"""Reglas de pantalla de Disposiciones (B13-FIX02, entry l. 67812-68550) sobre la sesion y el contexto de ``auth``.

Alcance (decisiones D1-D14, docs/disposiciones_analysis.md §33): las 3 pestañas certificadas (Configuracion, Nueva
disposicion, Historial).  No existen (y no se agregan) PDF, Excel, edicion o anulacion posterior de una disposicion,
regeneracion sobre la misma fila, reserva de numero, lock ni migracion de los Word heredados.

Cada writer certificado que la UI invoca es una operacion B12H propia (``correlation_id`` por writer):
1. comprobaciones de la pantalla sobre lecturas frescas (mismos mensajes que el certificado): sin evento;
2. B10 del writer (``disposiciones.write`` departamento; plantilla ``disposiciones.write`` INSTITUCION; eliminar
   ``disposiciones.delete`` -> solo superadmin): DENIED en transaccion propia;
3. B12I: SIN lock de capa T (D9); capa U: lo que el usuario vio se relee fresco (``huella``) en el primer writer del
   clic; en la generacion, al entrar a ``guardar_disposicion`` (despues de publicar el Word, que se borra si falla);
4. sus COMMITs certificados con SUCCESS (``commit_seq``); errores -> FAILED con ``coupled_commits``.  La plantilla (solo
   disco) registra SUCCESS ``POST_OPERATION`` con ``post_reason = FILESYSTEM_ONLY``.
El ambito sale SIEMPRE de la sesion revalidada; ningun id de tenant ni ruta de archivo llega del cliente.  Las descargas
(Word y ZIP) re-consultan la fila por id con el ambito de la sesion y validan dueño, referencia B12E, contencion en la
raiz y DOCX; las filas heredadas (ruta absoluta) quedan ``LEGACY_UNVERIFIED`` sin tocar el disco (D5).
"""

from __future__ import annotations

import base64
import binascii
import logging
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable, Optional

import pandas as pd
from psycopg import Connection

import audit
from auth import core, policy
from auth.service import AuthService, SessionRecord
from comisiones.service import _hash, _jsonable, _period
from periodos.service import MSG_AUDIT_POST, MSG_DB_READ, MSG_DB_TRANSACTION, MSG_INSTITUTIONAL, MSG_STALE
from periodos.service import denial_message, scope_message

from . import documents as D
from . import escrituras as E
from . import rules as R
from . import storage as S
from .lecturas import Lecturas, primera_designacion
from .repository import DisposicionesRepository

log = logging.getLogger("deptit_next.disposiciones")

MODULO = "disposiciones"
DEP = policy.SCOPE_DEPARTMENT
ACTION_READ = policy.Action(MODULO, policy.OP_READ, DEP)
ACTION_WRITE = policy.Action(MODULO, policy.OP_WRITE, DEP)
ACTION_DELETE = policy.Action(MODULO, policy.OP_DELETE, DEP)
ACTION_TEMPLATE = policy.Action(MODULO, policy.OP_WRITE, policy.SCOPE_INSTITUTION)
TEMPLATE_ADMIN_ROLES = frozenset({policy.ROLE_SUPERADMIN, policy.ROLE_DEPARTAMENTO})
MAX_TRANSPORTE_PLANTILLA = 2 * S.MAX_TEMPLATE_BYTES


@dataclass(frozen=True)
class WriterSpec:
    """Writer del registro B10 (``legacy_write_actions.py`` / B12E) y su etiqueta B12H (docs/audit/disposiciones_
    phase_a/b10_b12h_disposiciones.txt)."""
    name: str
    action: policy.Action
    entity_type: str
    entity_param: Optional[str]
    post_reason: str = "NO_POOLED_COMMIT"


SPEC_PARAMETROS = WriterSpec(E.W_PARAMETROS, ACTION_WRITE, "parametros_disposicion", None)
SPEC_PARAMETROS_DOCENTE = WriterSpec(E.W_PARAMETROS_DOCENTE, ACTION_WRITE, "parametros_disposicion", "cuil")
SPEC_DATOS_DESIGNACIONES = WriterSpec(E.W_DATOS_DESIGNACIONES, ACTION_WRITE, "designacion", "cuil")
SPEC_GENERAR = WriterSpec(E.W_GENERAR, ACTION_WRITE, "disposicion", "cuil")
SPEC_PLANTILLA = WriterSpec(E.W_PLANTILLA, ACTION_TEMPLATE, "plantilla_disposicion", None, "FILESYSTEM_ONLY")
SPEC_ELIMINAR = WriterSpec(E.W_ELIMINAR, ACTION_DELETE, "disposicion", None)

# --- textos certificados (entry l. 67812-68550) ------------------------------------------------------------------
INFO_PAGINA = ("Este módulo genera disposiciones en Word a partir de la plantilla con membrete de TU institución. "
               "Cada institución administra su propia plantilla en Configuración; no se usan rutas manuales.")
CAPTION_CONFIG = ("Estos datos se guardan de forma individual para el departamento actual y se reutilizan en sus "
                  "disposiciones y mensajes docentes.")
CAPTION_ACTO = ("El acto administrativo de cada designación se vincula desde el repositorio de Resoluciones y respaldos. "
                "Las disposiciones toman automáticamente el número del documento vinculado; los históricos todavía no "
                "vinculados conservan su referencia manual como compatibilidad.")
HELP_GENERO = "Define automáticamente Director/Directora en las disposiciones y en el mensaje de Resumen docente."
CAPTION_HABILITADOS = (
    "Solo aparecen docentes ACTIVOS con al menos una designación ACTIVA en este mismo período del departamento que "
    "estás analizando. Si un docente es compartido, cada departamento genera su propia disposición con su designación, "
    "resolución y funciones locales. Si es prestado, la disposición solo la genera el departamento de origen y además "
    "incorpora las funciones realizadas en los departamentos receptores. El N° se asigna por orden alfabético desde el "
    "número inicial configurado para el período.")
CAPTION_MASIVA_VALIDACION = (
    "Antes de generar, la app valida únicamente las designaciones concursadas/interinas activas del departamento "
    "actual. Las designaciones de un docente compartido en otros departamentos no se mezclan. En docentes prestados, la "
    "designación sigue siendo la del departamento de origen y solo se amplían las funciones que se informan.")
MSG_SIN_PERIODOS = "Primero necesitás tener períodos cargados."
MSG_SIN_HABILITADOS = "No hay docentes con designación activa en este período. No se puede generar una disposición nueva."
MSG_CONFIG_GUARDADA = "Configuración guardada."
MSG_PLANTILLA_REEMPLAZADA = "Plantilla de la institución reemplazada."
MSG_PLANTILLA_NO_DISPONIBLE = "La plantilla institucional no está disponible."
MSG_DATOS_GUARDADOS = "Datos guardados por designación y departamento."
MSG_GENERADA = "Disposición generada y guardada en historial. El botón de descarga queda disponible debajo."
MSG_NO_DOCENTE_SIN_TEXTO = ("Hay una designación no docente activa sin funciones cargadas. Completalas en el módulo "
                            "Designaciones antes de generar la disposición.")
MSG_LOTE_ERRORES = "No se pudo preparar el lote completo. Revisá los casos informados antes de generar."
MSG_LOTE_SIN_ACTO = ("No se generó ninguna disposición porque hay docentes con una designación concursada/interina activa "
                     "DEL DEPARTAMENTO ACTUAL sin acto administrativo vinculado al repositorio. Vinculá esos actos en "
                     "Designaciones.")
MSG_LOTE_NO_DOCENTE = ("No se generó ninguna disposición porque hay designaciones para funciones no docentes sin completar "
                       "sus funciones. Completalas en el módulo Designaciones antes de generar el lote.")
MSG_INCOMPLETAS = ("Hay designaciones activas sin acto administrativo vinculado al repositorio. Vinculalo en el módulo "
                   "Designaciones antes de emitir la disposición.")
MSG_SIN_HISTORIAL = "Todavía no hay disposiciones registradas."
MSG_ZIP_VACIO = "No hay archivos Word disponibles para descargar en conjunto con este filtro."
MSG_SELECCIONA_DESCARGA = "Seleccioná una disposición para descargar su Word."
MSG_CONFIRMAR_ELIMINAR = "Primero confirmá la eliminación."
MSG_ELIMINADO = "Registro eliminado. El archivo Word no se borra automáticamente."
MSG_VALOR_INVALIDO = "Uno de los valores enviados no es válido para este formulario."
MSG_SELECCION_INVALIDA = "La selección no corresponde a las filas mostradas. Actualizá la pantalla."
MSG_PERIODO_NO_ENCONTRADO = "No se encontró el período seleccionado."
MSG_PREPARACION = "No se pudo preparar la disposición: la lectura de sus datos falló."
MSG_GENERACION_DB = "la base de datos devolvió un error durante la operación"


class DisposicionesError(Exception):
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


def _named(row: dict) -> dict:
    return {"id": int(row["id"]), "nombre": row.get("nombre")}


def _id(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise DisposicionesError(422, "INVALID", MSG_VALOR_INVALIDO)
    return value


def _text(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        raise DisposicionesError(422, "INVALID", MSG_VALOR_INVALIDO)
    return str(value)


def _bool(value: Any) -> bool:
    if value in (None, ""):
        return False
    if not isinstance(value, bool):
        raise DisposicionesError(422, "INVALID", MSG_VALOR_INVALIDO)
    return value


def _fecha(value: Any) -> date:
    try:
        return date.fromisoformat(str(value))
    except Exception:
        raise DisposicionesError(422, "INVALID", MSG_VALOR_INVALIDO) from None


def _documento_status(exc: S.DocumentError) -> int:
    if isinstance(exc, S.DocxValidationError):
        return 422
    if isinstance(exc, S.DocumentUnavailable):
        return 503
    if isinstance(exc, S.DocumentAccessDenied):
        return 403 if exc.code in ("SCOPE_MISSING", "SCOPE_MISMATCH", "ROLE_NOT_PERMITTED",
                                   "SUPERADMIN_SELECTION_REQUIRED", "NO_AUTHORIZED_ACTOR") else 409
    return 503 if exc.code in ("STORAGE_ERROR", "OUTPUT_ALLOCATION_FAILED") else 400


# --- huellas B12I capa U (lo que el usuario vio) ------------------------------------------------------------------
def huella_fila_padron(r: Optional[dict]) -> str:
    if not r:
        return _hash(None)
    return _hash({"cuil": str(r.get("cuil") or ""), "nombre_completo": r.get("nombre_completo"),
                  "numero": int(r.get("numero_disposicion_auto") or 0)})


def huella_padron(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return _hash([])
    return _hash([huella_fila_padron(r) for r in df.to_dict("records")])


def huella_config(parametros: dict) -> str:
    return _hash({k: parametros.get(k, "") for k, _ in R.CAMPOS_CONFIGURACION})


def huella_disposicion(r: Optional[dict]) -> str:
    if not r:
        return _hash(None)
    return _hash({k: r.get(k) for k in ("id", "periodo_id", "numero", "cuil", "docente", "fecha", "tipo", "estado",
                                        "archivo_word")})


def huella_designaciones(datos: list[dict]) -> str:
    return _hash([{k: d.get(k) for k in ("designacion_id", "tipo_designacion", "cargo", "dedicacion", "resolucion",
                                         "fecha_desde", "fecha_hasta", "observaciones")} for d in datos])


def _records(df: Optional[pd.DataFrame], cols: list[str]) -> list[dict]:
    if df is None or df.empty:
        return []
    return [{c: _jsonable(r.get(c)) for c in cols} for r in df.to_dict("records")]


def _opciones_periodos(periodos: list[dict]) -> dict:
    """``{row["nombre"]: row["id"]}`` del certificado: un nombre repetido conserva su primera posicion y el ultimo id."""
    out: dict = {}
    for p in periodos:
        out[p.get("nombre")] = int(p["id"])
    return out


class DisposicionesService:
    def __init__(self, pool, auth: AuthService, audit_store: audit.AuditStore, *,
                 today: Callable[[], date] = date.today, now: Callable[[], datetime] = datetime.now,
                 transaction: Optional[Callable[[], AbstractContextManager[Connection]]] = None,
                 storage_root: Optional[Callable[[], str]] = None,
                 render: Optional[Callable[[str, str, dict, dict], Any]] = None):
        self.auth = auth
        self.audit_store = audit_store
        self.today = today
        self.now = now
        self._transaction = transaction or (lambda: pool.connection(timeout=5))
        self._root = storage_root or S.configured_root
        self._render = render or D.generar_word_desde_plantilla_disposicion

    # ------------------------------------------------------------------ contexto (B12B) y modulo visible
    def scope(self, record: SessionRecord) -> Scope:
        self.auth.apply_default_context(record)
        user, session_scope = record.user, record.scope
        visible = policy.visible_modules(policy.normalize_role(user.get("rol")),
                                         session_scope.get(policy.DEPARTMENT_SCOPE_KEY))
        resolution = self.auth.resolve_scope(record)
        if resolution.reason is not None:
            raise DisposicionesError(409, "SCOPE_NOT_VERIFIED", scope_message(resolution))
        if not any(m[0] == MODULO for m in visible) or resolution.department is None:
            raise DisposicionesError(409, "SCOPE_INSTITUTIONAL", MSG_INSTITUTIONAL)
        actor = policy.actor_from_session(user, session_scope)
        return Scope(int(resolution.institution["id"]), int(resolution.department["id"]), resolution.institution,
                     resolution.department, actor.role)

    def _require_read(self, record: SessionRecord) -> None:
        actor = policy.actor_from_session(record.user, record.scope)
        decision = policy.decide(actor, ACTION_READ)
        if not decision.allowed:
            raise DisposicionesError(403, "DENIED", denial_message(decision, ACTION_READ))

    def reader(self, record: SessionRecord) -> Scope:
        scope = self.scope(record)
        self._require_read(record)
        return scope

    def _read(self, scope: Scope, record: SessionRecord, fn: Callable[[Lecturas], Any]) -> Any:
        try:
            with self._transaction() as conn:
                conn.execute("SET TRANSACTION READ ONLY")
                repo = DisposicionesRepository(conn, scope.institution_id, scope.department_id)
                return fn(Lecturas(repo, self.today(), record.user.get("departamento_nombre") or ""))
        except DisposicionesError:
            raise
        except Exception as exc:
            log.error("disposiciones: lectura fallida: %s", type(exc).__name__)
            raise DisposicionesError(503, "DB_READ", MSG_DB_READ) from None

    def storage(self) -> S.DocumentStorage:
        return S.DocumentStorage(self._root())

    def _template_denial(self, record: SessionRecord, scope: Scope) -> Optional[str]:
        """``template_admin_denial`` B12E (mas estricto que B10): superadmin con la institucion ELEGIDA explicitamente y
        usuario_departamento de esa institucion."""
        actor = policy.actor_from_session(record.user, record.scope)
        decision = policy.decide(actor, ACTION_TEMPLATE)
        if not decision.allowed:
            return decision.code
        if actor.role not in TEMPLATE_ADMIN_ROLES:
            return "ROLE_NOT_PERMITTED"
        if actor.institution_id != scope.institution_id:
            return "SCOPE_MISMATCH"
        if actor.role == policy.ROLE_SUPERADMIN:
            selected = core.to_int_or_none(record.scope.get(policy.SUPERADMIN_INSTITUTION_KEY))
            if selected is None:
                return "SUPERADMIN_SELECTION_REQUIRED"
            if selected != actor.institution_id:
                return "SCOPE_MISMATCH"
        return None

    def _permisos(self, record: SessionRecord, scope: Scope) -> dict:
        actor = policy.actor_from_session(record.user, record.scope)
        return {"puede_escribir": policy.decide(actor, ACTION_WRITE).allowed,
                "puede_borrar": policy.decide(actor, ACTION_DELETE).allowed,
                "puede_plantilla": self._template_denial(record, scope) is None}

    # ------------------------------------------------------------------ B10 + B12H + B12I (capa U) por writer
    def _separate(self, op: audit.Operation, outcome: str, *, error_code: Optional[str] = None,
                  metadata: Optional[dict] = None) -> bool:
        mode = audit.MODE_POST_OPERATION if outcome == audit.OUTCOME_SUCCESS else audit.MODE_SEPARATE
        try:
            self.audit_store.append_separate(op.event(outcome, mode, error_code=error_code, metadata=metadata))
            return True
        except Exception as exc:
            log.error("B12H: el evento %s de %s no pudo persistirse (%s)", outcome, op.name, audit.error_code_of(exc))
            return False

    def _op(self, record: SessionRecord, scope: Scope, spec: WriterSpec, fn: Callable[[E.Unidad], Any], *,
            entity_raw: Any = None, stale: Optional[Callable[[], None]] = None) -> Any:
        """Un writer certificado completo: B10 -> B12I capa U -> sus COMMITs con SUCCESS, o FAILED (sin lock: D9)."""
        actor = policy.actor_from_session(record.user, record.scope)
        audit_actor = audit.actor_from_record(record.user, record.scope, record.meta)
        op = audit.Operation(spec.name, spec.action, spec.entity_type, audit_actor, spec.entity_param, entity_raw)
        decision = policy.decide(actor, spec.action)
        if not decision.allowed:
            self._separate(op, audit.OUTCOME_DENIED, error_code=decision.code, metadata={"b10_decision": decision.code})
            raise DisposicionesError(403, "DENIED", denial_message(decision, spec.action), "PermissionError")
        unidad = E.Unidad(self._transaction, op, scope.institution_id, scope.department_id, today=self.today(),
                          now=self.now(), usuario=str(record.user.get("email") or ""))

        def failed(error_code: str) -> None:
            self._separate(op, audit.OUTCOME_FAILED, error_code=error_code,
                           metadata={"coupled_commits": op.coupled_commits})
        try:
            if stale is not None:
                stale()
            result = fn(unidad)
        except DisposicionesError as exc:
            failed(exc.error_class)
            raise
        except S.DocumentError as exc:
            failed(audit.error_code_of(exc))
            raise DisposicionesError(_documento_status(exc), exc.code, str(exc), type(exc).__name__) from None
        except ValueError as exc:
            failed("ValueError")
            raise DisposicionesError(422, "REJECTED", str(exc)) from None
        except E.AuditoriaFallida:
            failed("AuditPersistenceError:AUDIT_INSERT_FAILED")
            raise DisposicionesError(503, "AUDIT", f"{audit.MSG_PERSIST} [AUDIT_INSERT_FAILED]",
                                     "AuditPersistenceError") from None
        except OSError as exc:
            log.error("disposiciones: %s falló en el almacenamiento: %s", spec.name, type(exc).__name__)
            failed(audit.error_code_of(exc))
            raise DisposicionesError(503, "STORAGE_ERROR", str(S.DocumentError("STORAGE_ERROR")),
                                     type(exc).__name__) from None
        except Exception as exc:
            log.error("disposiciones: %s falló tras %d COMMIT(s): %s", spec.name, op.coupled_commits,
                      type(exc).__name__)
            failed(audit.error_code_of(exc))
            raise DisposicionesError(503, "DB_ERROR", MSG_DB_TRANSACTION, type(exc).__name__) from None
        if op.coupled_commits == 0:
            if not self._separate(op, audit.OUTCOME_SUCCESS,
                                  metadata={"coupled_commits": 0, "post_reason": spec.post_reason}):
                raise DisposicionesError(503, "AUDIT", MSG_AUDIT_POST)
        return result

    def _stale(self, scope: Scope, record: SessionRecord, esperado: Any, fresh: Callable[[Lecturas], Any],
               label: str) -> Callable[[], None]:
        def check() -> None:
            try:
                actual = self._read(scope, record, fresh)
            except DisposicionesError:
                raise DisposicionesError(503, "FRESH_READ", MSG_DB_READ, "FreshReadError") from None
            if actual != esperado:
                raise DisposicionesError(409, "STALE", f"{MSG_STALE} [B12I: {label}]", "StaleDecisionError")
        return check

    # ------------------------------------------------------------------ comunes
    def _periodo_valido(self, scope: Scope, record: SessionRecord, periodo_id: Any) -> int:
        pid = _id(periodo_id)
        ids = set(_opciones_periodos(self._read(scope, record, lambda lec: lec.periodos())).values())
        if pid not in ids:
            raise DisposicionesError(404, "NOT_FOUND", MSG_PERIODO_NO_ENCONTRADO)
        return pid

    def _plantilla(self, scope: Scope) -> dict:
        try:
            st = S.template_status(self.storage(), scope.institution_id)
        except S.DocumentError as exc:
            st = {"status": "DENIED", "message": str(exc), "code": exc.code}
        st.pop("institucion_id", None)
        return st

    # ------------------------------------------------------------------ overview + Pestaña 1: Configuracion
    def overview(self, record: SessionRecord) -> dict:
        scope = self.reader(record)

        def read(lec: Lecturas):
            periodos = lec.periodos()
            opciones = _opciones_periodos(periodos)
            defecto = lec.periodo_por_defecto()
            nombre_def = defecto["nombre"] if defecto else (list(opciones.keys())[0] if opciones else None)
            parametros = lec.parametros()
            return {"periodos": [{"id": pid, "nombre": nombre} for nombre, pid in opciones.items()],
                    "periodo_defecto": opciones.get(nombre_def) if opciones else None,
                    "configuracion": {k: parametros.get(k, "") for k, _ in R.CAMPOS_CONFIGURACION},
                    "huella_configuracion": huella_config(parametros)}
        data = self._read(scope, record, read)
        return {"contexto": {"institucion": _named(scope.institution), "departamento": _named(scope.department)},
                **data, "rol": scope.rol, "permisos": self._permisos(record, scope), "info": INFO_PAGINA,
                "campos": [{"clave": k, "etiqueta": e} for k, e in R.CAMPOS_CONFIGURACION],
                "opciones_genero": R.OPCIONES_GENERO_AUTORIDAD, "estados": R.ESTADOS_DISPOSICION,
                "tipo_defecto": R.TIPO_DEFAULT, "plantilla": self._plantilla(scope),
                "textos": {"config": CAPTION_CONFIG, "acto": CAPTION_ACTO, "genero": HELP_GENERO,
                           "sin_periodos": MSG_SIN_PERIODOS}}

    def guardar_configuracion(self, record: SessionRecord, data: dict) -> dict:
        scope = self.reader(record)
        valores = data.get("valores")
        if not isinstance(valores, dict) or set(valores) != {k for k, _ in R.CAMPOS_CONFIGURACION}:
            raise DisposicionesError(422, "INVALID", MSG_VALOR_INVALIDO)
        nuevos = {k: _text(valores.get(k)) for k, _ in R.CAMPOS_CONFIGURACION}  # orden del formulario certificado
        if nuevos["genero_director_departamento"] not in R.OPCIONES_GENERO_AUTORIDAD:
            raise DisposicionesError(422, "INVALID", MSG_VALOR_INVALIDO)
        stale = self._stale(scope, record, data.get("huella"), lambda lec: huella_config(lec.parametros()),
                            "get_parametros_disposicion")
        self._op(record, scope, SPEC_PARAMETROS, lambda u: E.guardar_parametros_disposicion(u, nuevos), stale=stale)
        return {"mensaje": MSG_CONFIG_GUARDADA, "tono": "success"}

    def reemplazar_plantilla(self, record: SessionRecord, data: dict) -> dict:
        scope = self.reader(record)
        nombre = _text(data.get("nombre_archivo"))
        raw = data.get("contenido_base64")
        if not isinstance(raw, str) or not raw:
            raise DisposicionesError(422, "INVALID", MSG_VALOR_INVALIDO)
        # Limite de TRANSPORTE (el doble del maximo): un archivo apenas mayor llega al writer y falla su validacion
        # B12E (``DOCX_TOO_LARGE`` con FAILED), como en el certificado.
        if len(raw) > (MAX_TRANSPORTE_PLANTILLA * 4) // 3 + 8:
            raise DisposicionesError(413, "TOO_LARGE", str(S.DocxValidationError("DOCX_TOO_LARGE")))
        try:
            contenido = base64.b64decode(raw, validate=True)
        except (binascii.Error, ValueError):
            raise DisposicionesError(422, "DOCX_INVALID", str(S.DocxValidationError("DOCX_INVALID"))) from None

        def body(u: E.Unidad):
            denial = self._template_denial(record, scope)
            if denial:
                raise S.DocumentAccessDenied(denial)
            return E.reemplazar_plantilla(self.storage(), scope.institution_id, contenido, nombre)
        self._op(record, scope, SPEC_PLANTILLA, body)
        return {"mensaje": MSG_PLANTILLA_REEMPLAZADA, "tono": "success", "plantilla": self._plantilla(scope)}

    # ------------------------------------------------------------------ Pestaña 2: Nueva disposicion
    def periodo(self, record: SessionRecord, data: dict) -> dict:
        scope = self.reader(record)
        pid = self._periodo_valido(scope, record, data.get("periodo_id"))

        def read(lec: Lecturas):
            hab = lec.habilitados(pid)
            filas = _records(hab, ["numero_disposicion_auto", "nombre_completo", "cuil", "legajo", "titulo", "estado",
                                   "email"])
            for f in filas:
                f["huella"] = huella_fila_padron(f)
            return {"numero_inicial": lec.numero_inicial(pid), "habilitados": filas, "huella_padron": huella_padron(hab)}
        out = self._read(scope, record, read)
        out.update({"aviso": MSG_SIN_HABILITADOS if not out["habilitados"] else "", "caption": CAPTION_HABILITADOS,
                    "caption_validacion": CAPTION_MASIVA_VALIDACION, "plantilla": self._plantilla(scope)})
        return out

    def guardar_numero_inicial(self, record: SessionRecord, data: dict) -> dict:
        scope = self.reader(record)
        pid = self._periodo_valido(scope, record, data.get("periodo_id"))
        numero = data.get("numero")
        if isinstance(numero, bool) or not isinstance(numero, int) or numero < 1:  # number_input min_value=1, step 1
            raise DisposicionesError(422, "INVALID", MSG_VALOR_INVALIDO)
        stale = self._stale(scope, record, data.get("huella"), lambda lec: lec.numero_inicial(pid),
                            "get_numero_inicial_disposiciones_v162")
        guardado = self._op(record, scope, SPEC_PARAMETROS,
                            lambda u: E.guardar_numero_inicial_disposiciones_v162(u, pid, numero), stale=stale)
        return {"mensaje": f"El período comenzará en la disposición N° {int(guardado)}.", "tono": "success"}

    def _fila_padron(self, lec: Lecturas, pid: int, cuil: str) -> Optional[dict]:
        hab = lec.habilitados(pid)
        if hab is None or hab.empty:
            return None
        for r in hab.to_dict("records"):
            if str(r.get("cuil")) == cuil:
                return r
        return None

    def _docente_vista(self, lec: Lecturas, pid: int, cuil: str) -> dict:
        fila = self._fila_padron(lec, pid, cuil)
        if fila is None:
            raise DisposicionesError(409, "SELECCION", MSG_SELECCION_INVALIDA)
        ctx = lec.contexto(cuil, pid)
        ef = lec.estado_funcional(cuil, pid)
        texto_nd = lec.texto_funcion_no_docente(cuil, pid)
        asignaturas = ctx.get(R.CLAVE_ASIGNATURAS, ctx.get(R.CLAVE_ASIGNATURAS_LEGACY, ""))
        tiene_ie = bool(ctx.get("tiene_investigacion_o_extension", ctx.get("tiene_investigacion", False)))
        promover = bool(not ef.get("es_exclusivamente_no_docente") and not ef.get("es_mixta")
                        and not str(asignaturas or "").strip() and tiene_ie)
        datos = ctx.get("designaciones_disposicion", []) or []
        estado = lec.estado_consulta(cuil, pid)
        designaciones = []
        for x in datos:
            no_doc = R.es_funcion_no_docente_v162(x.get("funcion_no_docente"))
            horas = x.get("horas", "")
            designaciones.append({
                "designacion_id": _jsonable(x.get("designacion_id")), "departamento": x.get("departamento", ""),
                "tipo": x.get("tipo_designacion", ""), "cargo": x.get("cargo", ""),
                "dedicacion": x.get("dedicacion", ""),
                "horas": "" if horas is None or pd.isna(horas) else _jsonable(horas),
                "horas_texto": "" if horas is None or pd.isna(horas) else f" — {horas} horas",  # l. 68275
                "condicion": "Ad Honorem" if R.es_ad_honorem_v162(x.get("ad_honorem")) else "Rentada",
                "funcion": "No docente" if no_doc else "Docencia",
                "funciones_no_docentes": x.get("texto_funcion_no_docente", "") if no_doc else "",
                "texto_funcion_limpio": R.texto_funcion_no_docente_limpio_v164(x.get("texto_funcion_no_docente", ""))
                if no_doc else "",
                "resolucion": x.get("resolucion", ""), "fecha_desde": x.get("fecha_desde", ""),
                "fecha_hasta": x.get("fecha_hasta", ""), "observaciones": x.get("observaciones", ""),
            })
        return {
            "cuil": cuil, "numero": str(int(fila.get("numero_disposicion_auto") or 0)),
            "huella": huella_fila_padron(fila), "huella_designaciones": huella_designaciones(datos),
            "estado_consulta": R.estado_consulta_mostrado(estado.get("estado", "")),
            "docente": ctx.get("docente", ""), "cargo": ctx.get("cargo", ""), "dedicacion": ctx.get("dedicación", ""),
            "departamentos_revistara": ctx.get("texto_departamentos_revistara", ""), "asignaturas": asignaturas,
            "escuelas": ctx.get("Escuelas en las que se encuentran las materias que dicta", ""),
            "tiene_concursado": bool(ctx.get("tiene_concursado", False)),
            "tiene_interino": bool(ctx.get("tiene_interino", False)), "tiene_investigacion_o_extension": tiene_ie,
            "tiene_actividades_especiales": bool(ctx.get("tiene_actividades_especiales", False)),
            "designaciones": designaciones,
            "es_no_docente": bool(ef.get("es_exclusivamente_no_docente")), "es_mixta": bool(ef.get("es_mixta")),
            "tiene_no_docente": bool(ef.get("tiene_no_docente")), "texto_funcion_no_docente": texto_nd,
            "promover_ie_art1": promover, "observaciones_generales": lec.parametros_docente(cuil).get("observaciones", ""),
            "texto_investigacion": ctx.get("Texto funciones de investigación", ""),
            "rol_investigacion": ctx.get("Rol en su Proyecto de Investigación", ""),
            "proyecto_investigacion": ctx.get("Nombre Proyecto de Investigación", ""),
            "proyecto_extension": ctx.get("Nombre Proyecto de Extensión", ""),
            "codigo_investigacion": ctx.get("Código Interno del Proyecto", ""),
            "instituto_investigacion": ctx.get("Instituto/Departamento al que pertenece el proyecto", ""),
            "area_extension": ctx.get("Área/Secretaría al que pertenece el proyecto de Extensión", ""),
            "texto_actividades_especiales": str(ctx.get("Texto Actividades Especiales", "") or "").strip(),
            "ambito": ctx.get("ambito_disposicion", ""),
        }

    def docente(self, record: SessionRecord, data: dict) -> dict:
        scope = self.reader(record)
        pid = self._periodo_valido(scope, record, data.get("periodo_id"))
        cuil = _text(data.get("cuil"))
        out = self._read(scope, record, lambda lec: self._docente_vista(lec, pid, cuil))
        out.update(self._vista_previa(out["docente"] or cuil, cuil, self._formulario(out_designaciones(out), None),
                                      out["tiene_concursado"], out["tiene_interino"]))
        return out

    @staticmethod
    def _formulario(datos: list[dict], ediciones: Any) -> list[dict]:
        """``datos_designaciones_form`` (l. 68262-68300): cada designacion con las fechas/observaciones editadas.  El
        acto (``resolucion``) no se edita aca (solo lectura del repositorio)."""
        if ediciones is None:
            return [dict(d) for d in datos]
        if not isinstance(ediciones, list) or len(ediciones) != len(datos):
            raise DisposicionesError(409, "SELECCION", MSG_SELECCION_INVALIDA)
        form = []
        for dato, ed in zip(datos, ediciones):
            if not isinstance(ed, dict) or _jsonable(dato.get("designacion_id")) != ed.get("designacion_id"):
                raise DisposicionesError(409, "SELECCION", MSG_SELECCION_INVALIDA)
            form.append({**dato, "resolucion": dato.get("resolucion", ""), "fecha_desde": _text(ed.get("fecha_desde")),
                         "fecha_hasta": _text(ed.get("fecha_hasta")), "observaciones": _text(ed.get("observaciones"))})
        return form

    @staticmethod
    def _vista_previa(docente, cuil, form: list[dict], conc: bool, inter: bool) -> dict:
        considerandos = R.construir_considerandos_designaciones_docente(docente, cuil, form, incluir_concursado=conc,
                                                                        incluir_interino=inter)
        incompletas = [x for x in form if ((x.get("tipo_designacion") == "Concursado" and conc)
                                           or (x.get("tipo_designacion") == "Interino" and inter))
                       and not R.normalizar_texto_disposicion(x.get("resolucion"))]
        return {"considerandos": considerandos, "aviso_incompletas": MSG_INCOMPLETAS if incompletas else ""}

    def vista_previa(self, record: SessionRecord, data: dict) -> dict:
        scope = self.reader(record)
        pid = self._periodo_valido(scope, record, data.get("periodo_id"))
        cuil = _text(data.get("cuil"))
        conc, inter = _bool(data.get("incluir_concursado")), _bool(data.get("incluir_interino"))

        def read(lec: Lecturas):
            if self._fila_padron(lec, pid, cuil) is None:
                raise DisposicionesError(409, "SELECCION", MSG_SELECCION_INVALIDA)
            ctx = lec.contexto(cuil, pid)
            form = self._formulario(ctx.get("designaciones_disposicion", []) or [], data.get("designaciones"))
            return self._vista_previa(ctx.get("docente", cuil), cuil, form, conc, inter)
        return self._read(scope, record, read)

    def guardar_datos(self, record: SessionRecord, data: dict) -> dict:
        """"💾 Guardar datos de disposición para este docente" (l. 68305): 2 operaciones / 3 COMMIT."""
        scope = self.reader(record)
        pid = self._periodo_valido(scope, record, data.get("periodo_id"))
        cuil = _text(data.get("cuil"))
        obs = _text(data.get("observaciones_generales"))

        def read(lec: Lecturas):
            if self._fila_padron(lec, pid, cuil) is None:
                raise DisposicionesError(409, "SELECCION", MSG_SELECCION_INVALIDA)
            datos = lec.contexto(cuil, pid).get("designaciones_disposicion", []) or []
            return datos
        datos = self._read(scope, record, read)
        form = self._formulario(datos, data.get("designaciones") or [])

        def fresh(lec: Lecturas):
            return huella_designaciones(lec.contexto(cuil, pid).get("designaciones_disposicion", []) or [])
        stale = self._stale(scope, record, data.get("huella_designaciones"), fresh,
                            "get_datos_designaciones_docente_disposicion")
        self._op(record, scope, SPEC_DATOS_DESIGNACIONES,
                 lambda u: E.guardar_datos_designaciones_docente_disposicion(u, cuil, form), entity_raw=cuil, stale=stale)
        legacy = self._read(scope, record, lambda lec: lec.parametros_docente(cuil))
        legacy["observaciones"] = obs
        self._op(record, scope, SPEC_PARAMETROS_DOCENTE,
                 lambda u: E.guardar_parametros_docente_disposicion(u, cuil, legacy), entity_raw=cuil)
        return {"mensaje": MSG_DATOS_GUARDADOS, "tono": "success"}

    # ------------------------------------------------------------------ generacion individual (l. 68372-68454)
    def _variables_individuales(self, lec: Lecturas, pid: int, cuil: str, fila: dict, data: dict) -> dict:
        fecha = _fecha(data.get("fecha"))
        tipo = _text(data.get("tipo"))
        conc, inter = _bool(data.get("incluir_concursado")), _bool(data.get("incluir_interino"))
        es_investigador = _bool(data.get("incluir_investigacion"))
        numero_dispo = str(int(fila.get("numero_disposicion_auto") or 0))
        contexto_doc = lec.contexto(cuil, pid)
        parametros = lec.parametros()
        ef = lec.estado_funcional(cuil, pid)
        no_docente, mixta, tiene_no_docente = (bool(ef.get("es_exclusivamente_no_docente")), bool(ef.get("es_mixta")),
                                               bool(ef.get("tiene_no_docente")))
        texto_funcion = lec.texto_funcion_no_docente(cuil, pid)
        asignaturas_txt = contexto_doc.get(R.CLAVE_ASIGNATURAS, contexto_doc.get(R.CLAVE_ASIGNATURAS_LEGACY, ""))
        docente_nombre = contexto_doc.get("docente", "")
        form = self._formulario(contexto_doc.get("designaciones_disposicion", []) or [], data.get("designaciones"))
        considerandos = R.construir_considerandos_designaciones_docente(
            contexto_doc.get("docente", cuil), cuil, form, incluir_concursado=conc, incluir_interino=inter)
        primer_conc = primera_designacion(form, "Concursado")
        primer_int = primera_designacion(form, "Interino")
        texto_investigacion = contexto_doc.get("Texto funciones de investigación", "")
        variables = {}
        variables.update(parametros)
        variables.update(contexto_doc)
        variables.update({
            "Fecha Disposición": fecha.strftime("%d/%m/%Y"),
            "número_disposición": numero_dispo,
            "departamento_disposicion_encabezado": contexto_doc.get("texto_departamento_disposicion", "")
            or lec.texto_departamento_disposicion_docente(cuil, pid),
            "fecha": parametros.get("fecha_acta_rector", ""),
            "fecha_acta_rector": parametros.get("fecha_acta_rector", ""),
            "docente": docente_nombre,
            "cuil": cuil,
            "CUIL": cuil,
            "cargo": contexto_doc.get("cargo", ""),
            "dedicación": contexto_doc.get("dedicación", ""),
            "texto_departamentos_revistara": contexto_doc.get("texto_departamentos_revistara", ""),
            "departamento_revistara": contexto_doc.get("texto_departamentos_revistara", ""),
            R.CLAVE_ASIGNATURAS_LEGACY: asignaturas_txt,
            R.CLAVE_ASIGNATURAS: asignaturas_txt,
            "ES_FUNCION_NO_DOCENTE": no_docente,
            "ES_FUNCION_MIXTA": mixta,
            "Texto función no docente": str(texto_funcion or "").strip() if tiene_no_docente else "",
            "Texto variable Artículo 1": str(texto_funcion or "").strip() if tiene_no_docente else "",
            "Escuelas en las que se encuentran las materias que dicta":
                contexto_doc.get("Escuelas en las que se encuentran las materias que dicta", ""),
            "fecha_desde_interino": primer_int.get("fecha_desde", ""),
            "fecha_hasta_interino": primer_int.get("fecha_hasta", ""),
            "Rol en su Proyecto de Investigación": contexto_doc.get("Rol en su Proyecto de Investigación", ""),
            "Nombre Proyecto de Investigación": contexto_doc.get("Nombre Proyecto de Investigación", ""),
            "Código Interno del Proyecto": contexto_doc.get("Código Interno del Proyecto", ""),
            "Instituto/Departamento al que pertenece el proyecto":
                contexto_doc.get("Instituto/Departamento al que pertenece el proyecto", ""),
            "Texto funciones de investigación": texto_investigacion,
            "Texto funciones de investigación y extensión": texto_investigacion,
            "Tipo funciones investigación/extensión": contexto_doc.get("Tipo funciones investigación/extensión",
                                                                       "investigación"),
            "considerandos_designaciones": considerandos,
            "designaciones_disposicion": form,
            "resolucion_cs_concursado": primer_conc.get("resolucion", ""),
            "resolucion_cs_interino": primer_int.get("resolucion", ""),
            "resolucion_rectoral_interino": primer_int.get("resolucion", ""),
            "fecha_desde_concursado": primer_conc.get("fecha_desde", ""),
            "fecha_hasta_concursado": primer_conc.get("fecha_hasta", ""),
        })
        condiciones = {"SI_TIENE_CONCURSADO": conc, "SI_TIENE_INTERINO": inter, "SI_INVESTIGADOR": es_investigador,
                       "SI_NO_INVESTIGA": not es_investigador}
        return {"fecha": fecha, "tipo": tipo, "numero": numero_dispo, "docente": docente_nombre, "variables": variables,
                "condiciones": condiciones, "bloqueo_no_docente": bool(tiene_no_docente and not str(texto_funcion or "")
                                                                       .strip())}

    def _stale_fila(self, scope: Scope, record: SessionRecord, pid: int, cuil: str, huella: Any) -> Callable[[], None]:
        return self._stale(scope, record, huella,
                           lambda lec: huella_fila_padron(self._fila_padron(lec, pid, cuil)),
                           "get_docentes_activos_para_disposiciones_v155")

    def generar(self, record: SessionRecord, data: dict) -> dict:
        scope = self.reader(record)
        pid = self._periodo_valido(scope, record, data.get("periodo_id"))
        cuil = _text(data.get("cuil"))
        estado = _text(data.get("estado"))
        if estado not in R.ESTADOS_DISPOSICION:
            raise DisposicionesError(422, "INVALID", MSG_VALOR_INVALIDO)
        observaciones = _text(data.get("observaciones"))

        def read(lec: Lecturas):
            fila = self._fila_padron(lec, pid, cuil)
            if fila is None or huella_fila_padron(fila) != data.get("huella"):
                raise DisposicionesError(409, "SELECCION", MSG_SELECCION_INVALIDA)
            return self._variables_individuales(lec, pid, cuil, fila, data)
        prep = self._read(scope, record, read)
        if prep["bloqueo_no_docente"]:
            raise DisposicionesError(422, "VALIDATION", MSG_NO_DOCENTE_SIN_TEXTO)
        detalle = f"Disposición generada para {prep['docente']} - {prep['tipo']}"
        try:
            generado = self._generar_op(record, scope, pid, prep["fecha"], prep["tipo"], prep["numero"], cuil,
                                        prep["docente"], detalle, observaciones, estado, prep["variables"],
                                        prep["condiciones"], self._stale_fila(scope, record, pid, cuil, data.get("huella")))
        except DisposicionesError as exc:
            if exc.code in ("DENIED", "STALE", "FRESH_READ"):
                raise
            raise DisposicionesError(exc.status, exc.code, f"No se pudo generar el Word: {exc.message}",
                                     exc.error_class) from None
        return {"mensaje": MSG_GENERADA, "tono": "success", "id": generado["id"], "file_name": generado["file_name"]}

    def _generar_op(self, record, scope, pid, fecha, tipo, numero, cuil, docente, detalle, observaciones, estado,
                    variables, condiciones, stale) -> dict:
        def body(u: E.Unidad):
            if not (scope.institution_id and scope.department_id):  # ``generation_denial`` B12E
                raise S.DocumentAccessDenied("SCOPE_MISSING")
            return E.generar_disposicion_word(u, self.storage(), self._render, pid, fecha, tipo, numero, cuil, docente,
                                              detalle, observaciones, estado, variables, condiciones, stale=stale)
        return self._op(record, scope, SPEC_GENERAR, body, entity_raw=cuil)

    # ------------------------------------------------------------------ generacion masiva (D10, l. 67923-68076)
    def generar_masiva(self, record: SessionRecord, data: dict) -> dict:
        scope = self.reader(record)
        pid = self._periodo_valido(scope, record, data.get("periodo_id"))
        fecha = _fecha(data.get("fecha"))
        tipo = _text(data.get("tipo"))
        estado = _text(data.get("estado"))
        if estado not in R.ESTADOS_DISPOSICION:
            raise DisposicionesError(422, "INVALID", MSG_VALOR_INVALIDO)
        plantilla = self._plantilla(scope)
        if plantilla.get("status") != "OK":
            raise DisposicionesError(409, "TEMPLATE", plantilla.get("message") or MSG_PLANTILLA_NO_DISPONIBLE)

        # FASE 1: preparacion del lote COMPLETO (una sola lectura).  Cualquier problema -> ningun documento.
        def preparar(lec: Lecturas):
            hab = lec.habilitados(pid)
            if huella_padron(hab) != data.get("huella_padron"):
                raise DisposicionesError(409, "SELECCION", MSG_SELECCION_INVALIDA)
            nombre_periodo = next((n for n, i in _opciones_periodos(lec.periodos()).items() if i == pid), "")
            parametros = lec.parametros()
            preparados, sin_acto, sin_funcion, errores = [], [], [], []
            for row in (hab.to_dict("records") if hab is not None else []):
                cuil_m = str(row.get("cuil") or "").strip()
                numero_m = str(int(row.get("numero_disposicion_auto") or 0))
                try:
                    with lec.repo._conn.transaction():
                        prep = lec.preparar(cuil_m, pid, numero_m, fecha, parametros=parametros)
                except Exception as exc:
                    log.error("disposiciones: preparación fallida: %s", type(exc).__name__)
                    errores.append({"N° disposición": numero_m,
                                    "Docente": R.limpiar_texto_tabla(row.get("nombre_completo", "")) or cuil_m,
                                    "Error": MSG_PREPARACION})
                    continue
                preparados.append(prep)
                if prep.get("designaciones_incompletas"):
                    sin_acto.append({"N° disposición": numero_m, "Docente": prep.get("docente", cuil_m), "CUIL": cuil_m})
                if prep.get("funcion_no_docente_sin_texto"):
                    sin_funcion.append({"N° disposición": numero_m, "Docente": prep.get("docente", cuil_m),
                                        "CUIL": cuil_m})
            return preparados, sin_acto, sin_funcion, errores, nombre_periodo
        preparados, sin_acto, sin_funcion, errores, nombre_periodo = self._read(scope, record, preparar)
        bloqueo = ((MSG_LOTE_ERRORES, errores) if errores else (MSG_LOTE_SIN_ACTO, sin_acto) if sin_acto
                   else (MSG_LOTE_NO_DOCENTE, sin_funcion) if sin_funcion else None)
        if bloqueo is not None:
            return {"tono": "error", "mensaje": bloqueo[0], "tabla": bloqueo[1], "generadas": 0, "ids": [],
                    "errores": []}

        # FASE 2: N operaciones independientes, SECUENCIALES, con la semantica de la generacion individual.
        primera = {"stale": self._stale(scope, record, data.get("huella_padron"),
                                        lambda lec: huella_padron(lec.habilitados(pid)),
                                        "get_docentes_activos_para_disposiciones_v155")}

        def tomar_stale():
            # El registro de lecturas B12I se vacia despues de cada writer: solo la primera operacion revalida.
            s, primera["stale"] = primera["stale"], None
            return s
        generados, errores_generacion = [], []
        for prep in preparados:
            cuil_m, docente_m, numero_m = prep["cuil"], prep["docente"], prep["numero"]
            try:
                g = self._generar_op(record, scope, pid, fecha, tipo, numero_m, cuil_m, docente_m,
                                     f"Disposición generada para {docente_m} - {tipo}", R.OBS_MASIVA, estado,
                                     prep["variables"], prep["condiciones"], tomar_stale())
                generados.append(g["id"])
            except DisposicionesError as exc:
                if exc.code == "DENIED":  # ``st.error`` + ``st.stop()`` del certificado: corta el lote
                    raise
                errores_generacion.append({"N° disposición": numero_m, "Docente": docente_m, "Error": exc.message})
        out = {"generadas": len(generados), "ids": generados, "errores": errores_generacion, "tabla": [],
               "zip_nombre": f"{R.nombre_archivo_seguro('Disposiciones_' + str(nombre_periodo))}.zip"}
        if generados:
            out.update({"tono": "success", "mensaje": f"Se generaron y guardaron {len(generados)} disposiciones del "
                                                      "período. Ya podés descargar el ZIP debajo."})
        else:
            out.update({"tono": "warning", "mensaje": ""})
        if errores_generacion:
            out["aviso"] = (f"Hubo {len(errores_generacion)} disposición/es que no pudieron generarse. Las restantes sí "
                            "quedaron guardadas.")
        return out

    # ------------------------------------------------------------------ Pestaña 3: Historial
    def _payloads(self, scope: Scope, record: SessionRecord, filas: list[dict]) -> tuple[list, dict, dict]:
        """``history_zip`` B12E: cada fila se RE-CONSULTA por id con el ambito de la sesion; heredadas, ajenas y
        faltantes se omiten y se informan (las heredadas sin tocar el disco)."""
        meta: dict = {}
        for fila in list(filas or [])[:S.MAX_HISTORY_IDS]:
            fid = core.to_int_or_none(fila.get("id")) if hasattr(fila, "get") else None
            if fid is not None and fid > 0 and fid not in meta:
                meta[fid] = fila
        if not meta:
            return [], {}, {}
        try:
            rows = self._read(scope, record, lambda lec: {core.to_int_or_none(r.get("id")): r for r in
                                                          lec.repo.filas_dueno(sorted(meta)).to_dict("records")})
        except DisposicionesError:
            raise DisposicionesError(503, "DB_UNAVAILABLE", str(S.DocumentUnavailable("DB_UNAVAILABLE"))) from None
        storage = self.storage()
        items, skipped, estados = [], {}, {}
        for fid, fila in meta.items():
            row = rows.get(fid)
            try:
                if row is None:
                    raise S.DocumentAccessDenied("NOT_FOUND")
                payload = S.payload_for_row(storage, row, scope.institution_id, scope.department_id)
            except S.DocumentError as exc:
                skipped[exc.code] = skipped.get(exc.code, 0) + 1
                estados[fid] = str(exc)
                continue
            estados[fid] = None
            label = (f"{fila.get('periodo') or 'periodo'}_Disposicion_{fila.get('numero') or 'sin_numero'}_"
                     f"{fila.get('docente') or fila.get('cuil') or 'docente'}")
            items.append((label, payload))
        return items, skipped, estados

    def historial(self, record: SessionRecord, data: dict) -> dict:
        scope = self.reader(record)
        pid = None if data.get("periodo_id") in (None, "") else self._periodo_valido(scope, record, data.get("periodo_id"))
        filas = self._read(scope, record, lambda lec: lec.historial(pid).to_dict("records"))
        if not filas:
            return {"filas": [], "mensaje": MSG_SIN_HISTORIAL, "zip": {"cantidad": 0, "total": 0},
                    "permisos": self._permisos(record, scope)}
        try:
            items, _skipped, estados = self._payloads(scope, record, filas)
            zip_error = ""
        except DisposicionesError as exc:
            items, estados, zip_error = [], {}, exc.message
        cols = ["id", "periodo", "numero", "docente", "cuil", "fecha", "tipo", "estado", "observaciones"]
        out = []
        for f in filas:
            row = {c: _jsonable(f.get(c)) for c in cols}
            row["huella"] = huella_disposicion(f)
            mensaje = estados.get(core.to_int_or_none(f.get("id")), str(S.DocumentUnavailable("DB_UNAVAILABLE")))
            row["documento"] = {"disponible": mensaje is None, "mensaje": mensaje or "",
                                "legado": S.estado_documento(f.get("archivo_word")) == "LEGACY_UNVERIFIED"}
            out.append(row)
        cantidad = len(items)
        zip_info = {"cantidad": cantidad, "total": len(filas), "error": zip_error,
                    "aviso": "" if cantidad else MSG_ZIP_VACIO,
                    "detalle": (f"Se incluyeron {cantidad} de {len(filas)} registros: algunos Word no están disponibles "
                                "o son históricos anteriores a B12E (bloqueados hasta la migración controlada).")
                    if 0 < cantidad < len(filas) else ""}
        return {"filas": out, "mensaje": "", "zip": zip_info, "permisos": self._permisos(record, scope),
                "texto_seleccion": MSG_SELECCIONA_DESCARGA}

    def descargar(self, record: SessionRecord, data: dict) -> S.DocumentPayload:
        """``descargar_disposicion_historial_b12e`` (también para el Word recien generado)."""
        scope = self.reader(record)
        did = core.to_int_or_none(data.get("id"))
        if did is None or did <= 0 or isinstance(data.get("id"), bool):
            raise DisposicionesError(400, "INVALID_ID", str(S.DocumentAccessDenied("INVALID_ID")))
        rows = self._read(scope, record, lambda lec: lec.repo.filas_dueno([did]).to_dict("records"))
        try:
            if len(rows) != 1 or core.to_int_or_none(rows[0].get("id")) != did:
                raise S.DocumentAccessDenied("NOT_FOUND")
            return S.payload_for_row(self.storage(), rows[0], scope.institution_id, scope.department_id)
        except S.DocumentError as exc:
            raise DisposicionesError(_documento_status(exc), exc.code, str(exc), type(exc).__name__) from None

    def zip_historial(self, record: SessionRecord, data: dict) -> tuple[bytes, str]:
        scope = self.reader(record)
        pid = None if data.get("periodo_id") in (None, "") else self._periodo_valido(scope, record, data.get("periodo_id"))
        filas = self._read(scope, record, lambda lec: lec.historial(pid).to_dict("records"))
        items, _, _ = self._payloads(scope, record, filas)
        contenido, n = S.zip_payloads((label, p.data) for label, p in items)
        if not n:
            raise DisposicionesError(404, "ZIP_EMPTY", MSG_ZIP_VACIO, tone="warning")
        if pid is None:
            etiqueta = "Todos los períodos"
        else:
            etiqueta = next((nm for nm, i in _opciones_periodos(self._read(scope, record, lambda lec: lec.periodos()))
                             .items() if i == pid), "")
        return contenido, f"{R.nombre_archivo_seguro('Disposiciones_' + str(etiqueta))}.zip"

    def zip_lote(self, record: SessionRecord, data: dict) -> tuple[bytes, str]:
        """ZIP del lote recien generado (``zip_disposiciones_generadas_b12e``): mismos Word, mismas etiquetas
        "{período}_Disposicion_{N°}_{docente}", servidos por el camino seguro B12E (ids re-consultados)."""
        scope = self.reader(record)
        pid = self._periodo_valido(scope, record, data.get("periodo_id"))
        ids = data.get("ids")
        if not isinstance(ids, list) or not ids or any(isinstance(i, bool) or not isinstance(i, int) for i in ids):
            raise DisposicionesError(422, "INVALID", MSG_VALOR_INVALIDO)
        historial = self._read(scope, record, lambda lec: {int(f["id"]): f for f in lec.historial(pid).to_dict("records")})
        filas = [historial[i] for i in ids if i in historial]
        items, _, _ = self._payloads(scope, record, filas)
        contenido, n = S.zip_payloads((label, p.data) for label, p in items)
        if not n:
            raise DisposicionesError(404, "ZIP_EMPTY", MSG_ZIP_VACIO, tone="warning")
        nombre = next((nm for nm, i in _opciones_periodos(self._read(scope, record, lambda lec: lec.periodos()))
                       .items() if i == pid), "")
        return contenido, f"{R.nombre_archivo_seguro('Disposiciones_' + str(nombre))}.zip"

    def eliminar(self, record: SessionRecord, data: dict) -> dict:
        scope = self.reader(record)
        did = _id(data.get("id"))

        def fila_actual(lec: Lecturas):
            return next((f for f in lec.historial(None).to_dict("records") if int(f["id"]) == did), None)
        fila = self._read(scope, record, fila_actual)
        if fila is None or huella_disposicion(fila) != data.get("huella"):
            raise DisposicionesError(409, "SELECCION", MSG_SELECCION_INVALIDA)
        if not _bool(data.get("confirmar")):
            raise DisposicionesError(422, "VALIDATION", MSG_CONFIRMAR_ELIMINAR)
        stale = self._stale(scope, record, data.get("huella"), lambda lec: huella_disposicion(fila_actual(lec)),
                            "get_disposiciones")
        self._op(record, scope, SPEC_ELIMINAR, lambda u: E.eliminar_disposicion(u, did), entity_raw=did, stale=stale)
        return {"mensaje": MSG_ELIMINADO, "tono": "warning"}


def out_designaciones(vista: dict) -> list[dict]:
    """Designaciones del contexto en la forma de ``datos_designaciones_form`` (para la vista previa inicial)."""
    return [{"designacion_id": d["designacion_id"], "tipo_designacion": d["tipo"], "departamento": d["departamento"],
             "cargo": d["cargo"], "dedicacion": d["dedicacion"],
             "ad_honorem": "Sí" if d["condicion"] == "Ad Honorem" else "No", "resolucion": d["resolucion"],
             "fecha_desde": d["fecha_desde"], "fecha_hasta": d["fecha_hasta"], "observaciones": d["observaciones"]}
            for d in vista["designaciones"]]


__all__ = ["DisposicionesService", "DisposicionesError", "huella_fila_padron", "huella_padron", "huella_config",
           "huella_disposicion", "huella_designaciones"]
