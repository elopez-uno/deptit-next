"""Reglas de pantalla de Actividades Especiales (B13-FIX02, entry l. 66418-66603) sobre la sesion y el contexto de ``auth``.

Alcance (decisiones G1-G9, docs/actividades_especiales_analysis.md §18): las 5 pestañas certificadas y sus 5 writers.
No existen (y no se agregan) horas, Excel, actos, costos, movimientos, bajas ni reactivacion de participaciones.

Cada writer certificado que la UI invoca es una operacion B12H propia (``correlation_id`` por writer):
1. comprobaciones de la pantalla sobre lecturas frescas (mismos mensajes que el certificado): sin evento;
2. B10 del writer (``actividades_especiales.write`` / ``actividades_especiales.delete``, alcance departamento): DENIED en
   transaccion propia;
3. B12I: SIN lock de capa T (ninguna familia certificada incluye estos writers, G4); capa U: en el primer writer del
   clic se relee fresco lo que el usuario vio (``huella``); si cambio -> FAILED ``StaleDecisionError`` sin escribir;
4. el COMMIT certificado con su SUCCESS (``commit_seq``) en esa transaccion; ``ValueError`` del writer (titulo o rol
   vacio, actividad inexistente, duplicado) -> FAILED; error de base -> FAILED con ``coupled_commits`` (B12D).
El ambito (institucion/departamento) sale SIEMPRE de la sesion revalidada; ningun id de tenant llega del cliente.
Periodos (G3): cualquier periodo del departamento, abierto o cerrado; sin foto al cierre ni vigencia.
"""

from __future__ import annotations

import logging
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable, Optional

import pandas as pd
from psycopg import Connection

import audit
from auth import policy
from auth.service import AuthService, SessionRecord
from comisiones.service import _hash, _period, records
from docentes.repository import DocentesRepository
from periodos.service import MSG_AUDIT_POST, MSG_DB_READ, MSG_DB_TRANSACTION, MSG_INSTITUTIONAL, MSG_STALE
from periodos.service import denial_message, scope_message

from . import escrituras as E
from . import rules as AR
from .repository import ActividadesRepository

log = logging.getLogger("deptit_next.actividades_especiales")

MODULO = "actividades_especiales"
DEP = policy.SCOPE_DEPARTMENT
ACTION_READ = policy.Action(MODULO, policy.OP_READ, DEP)
ACTION_WRITE = policy.Action(MODULO, policy.OP_WRITE, DEP)
ACTION_DELETE = policy.Action(MODULO, policy.OP_DELETE, DEP)


@dataclass(frozen=True)
class WriterSpec:
    """Writer del registro B10 (legacy_write_actions.py l. 222-227) y su etiqueta B12H (``entity_type_for`` /
    ``_entity_param`` certificados: docs/audit/actividades_especiales_phase_a/b12h_entidades.txt)."""
    name: str
    action: policy.Action
    entity_type: str
    entity_param: Optional[str]


ENTIDAD = "actividad_especial"
SPEC_GUARDAR = WriterSpec(E.W_GUARDAR, ACTION_WRITE, ENTIDAD, "periodo_id")
SPEC_ACTUALIZAR = WriterSpec(E.W_ACTUALIZAR, ACTION_WRITE, ENTIDAD, "actividad_id")
SPEC_ASIGNAR = WriterSpec(E.W_ASIGNAR, ACTION_WRITE, ENTIDAD, "actividad_id")
SPEC_ELIMINAR = WriterSpec(E.W_ELIMINAR, ACTION_DELETE, ENTIDAD, "actividad_id")
SPEC_ELIMINAR_ASIGNACION = WriterSpec(E.W_ELIMINAR_ASIGNACION, ACTION_DELETE, ENTIDAD, "asignacion_id")

# --- textos certificados (entry l. 66418-66603) ----------------------------------------------------------------
MSG_VALOR_INVALIDO = "Uno de los valores enviados no es válido para este formulario."
MSG_SELECCION_INVALIDA = "La selección no corresponde a las filas mostradas. Actualizá la pantalla."
MSG_PERIODO_NO_ENCONTRADO = "No se encontró el período seleccionado."
MSG_CREADA = "Actividad Especial creada correctamente."
MSG_SIN_DOCENTES = "Seleccioná al menos un docente."
MSG_SIN_ROL = "Indicá el rol de cada docente."
MSG_ACTUALIZADA = "Actividad actualizada."
MSG_PARTICIPACION_ELIMINADA = "Participación eliminada."
MSG_CONFIRMAR_ELIMINAR = "Confirmá la eliminación por error."
MSG_ELIMINADA = "Actividad y participaciones eliminadas."
INFO_PAGINA = ("Registrá participaciones especiales del período. Estas actividades no consumen horas de dedicación, "
               "no ocupan el cronograma semanal y, cuando corresponda, se incorporan automáticamente como Artículo 3° "
               "de la disposición docente.")


class ActividadesError(Exception):
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
        raise ActividadesError(422, "INVALID", MSG_VALOR_INVALIDO)
    return value


def _text(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        raise ActividadesError(422, "INVALID", MSG_VALOR_INVALIDO)
    return str(value)


def _bool(value: Any) -> bool:
    if value in (None, ""):
        return False
    if not isinstance(value, bool):
        raise ActividadesError(422, "INVALID", MSG_VALOR_INVALIDO)
    return value


# --- huellas B12I capa U (lo que el usuario vio) ------------------------------------------------------------------
def huella_actividad(a: Optional[dict]) -> str:
    if not a:
        return _hash(None)
    return _hash({k: a.get(k) for k in ("id", "periodo_id", "titulo", "descripcion", "estado", "observaciones",
                                        "fecha_carga")})


def huella_participacion(p: Optional[dict]) -> str:
    if not p:
        return _hash(None)
    return _hash({k: p.get(k) for k in ("id", "actividad_id", "periodo_id", "cuil", "rol", "estado_asignacion",
                                        "observaciones")})


def _con_huella(rows: list[dict], fn: Callable[[dict], str]) -> list[dict]:
    for r in rows:
        r["huella"] = fn(r)
    return rows


class ActividadesService:
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
            raise ActividadesError(409, "SCOPE_NOT_VERIFIED", scope_message(resolution))
        if not any(m[0] == MODULO for m in visible) or resolution.department is None:
            raise ActividadesError(409, "SCOPE_INSTITUTIONAL", MSG_INSTITUTIONAL)
        actor = policy.actor_from_session(user, session_scope)
        return Scope(int(resolution.institution["id"]), int(resolution.department["id"]), resolution.institution,
                     resolution.department, actor.role)

    def _require_read(self, record: SessionRecord) -> None:
        actor = policy.actor_from_session(record.user, record.scope)
        decision = policy.decide(actor, ACTION_READ)
        if not decision.allowed:
            raise ActividadesError(403, "DENIED", denial_message(decision, ACTION_READ))

    def _read(self, scope: Scope, fn: Callable[[ActividadesRepository], Any]) -> Any:
        try:
            with self._transaction() as conn:
                conn.execute("SET TRANSACTION READ ONLY")
                return fn(ActividadesRepository(conn, scope.institution_id, scope.department_id))
        except ActividadesError:
            raise
        except Exception as exc:
            log.error("actividades_especiales: lectura fallida: %s", type(exc).__name__)
            raise ActividadesError(503, "DB_READ", MSG_DB_READ) from None

    def reader(self, record: SessionRecord) -> Scope:
        scope = self.scope(record)
        self._require_read(record)
        return scope

    def _permisos(self, record: SessionRecord) -> dict:
        actor = policy.actor_from_session(record.user, record.scope)
        return {"puede_escribir": policy.decide(actor, ACTION_WRITE).allowed,
                "puede_borrar": policy.decide(actor, ACTION_DELETE).allowed}

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
        """Un writer certificado completo: B10 -> B12I capa U -> su COMMIT con SUCCESS, o FAILED (sin lock: G4)."""
        actor = policy.actor_from_session(record.user, record.scope)
        audit_actor = audit.actor_from_record(record.user, record.scope, record.meta)
        op = audit.Operation(spec.name, spec.action, spec.entity_type, audit_actor, spec.entity_param, entity_raw)
        decision = policy.decide(actor, spec.action)
        if not decision.allowed:
            self._separate(op, audit.OUTCOME_DENIED, error_code=decision.code, metadata={"b10_decision": decision.code})
            raise ActividadesError(403, "DENIED", denial_message(decision, spec.action), "PermissionError")
        unidad = E.Unidad(self._transaction, op, scope.institution_id, scope.department_id, today=self.today(),
                          now=self.now(), usuario=str(record.user.get("email") or ""))
        try:
            if stale is not None:
                stale()
            result = fn(unidad)
        except ActividadesError as exc:
            self._separate(op, audit.OUTCOME_FAILED, error_code=exc.error_class,
                           metadata={"coupled_commits": op.coupled_commits})
            raise
        except ValueError as exc:
            self._separate(op, audit.OUTCOME_FAILED, error_code="ValueError",
                           metadata={"coupled_commits": op.coupled_commits})
            raise ActividadesError(422, "REJECTED", str(exc)) from None
        except E.AuditoriaFallida:
            self._separate(op, audit.OUTCOME_FAILED, error_code="AuditPersistenceError:AUDIT_INSERT_FAILED",
                           metadata={"coupled_commits": op.coupled_commits})
            raise ActividadesError(503, "AUDIT", f"{audit.MSG_PERSIST} [AUDIT_INSERT_FAILED]",
                                   "AuditPersistenceError") from None
        except Exception as exc:
            log.error("actividades_especiales: %s falló tras %d COMMIT(s): %s", spec.name, op.coupled_commits,
                      type(exc).__name__)
            self._separate(op, audit.OUTCOME_FAILED, error_code=audit.error_code_of(exc),
                           metadata={"coupled_commits": op.coupled_commits})
            raise ActividadesError(503, "DB_ERROR", MSG_DB_TRANSACTION) from None
        if op.coupled_commits == 0:
            if not self._separate(op, audit.OUTCOME_SUCCESS,
                                  metadata={"coupled_commits": 0, "post_reason": "NO_POOLED_COMMIT"}):
                raise ActividadesError(503, "AUDIT", MSG_AUDIT_POST)
        return result

    def _stale(self, scope: Scope, esperado: Any, fresh: Callable[[ActividadesRepository], Any],
               label: str) -> Callable[[], None]:
        """B12I capa U: lo que el usuario vio se relee fresco antes del primer SQL del writer."""
        def check() -> None:
            try:
                actual = self._read(scope, fresh)
            except ActividadesError:
                raise ActividadesError(503, "FRESH_READ", MSG_DB_READ, "FreshReadError") from None
            if actual != esperado:
                raise ActividadesError(409, "STALE", f"{MSG_STALE} [B12I: {label}]", "StaleDecisionError")
        return check

    # ------------------------------------------------------------------ lecturas comunes
    @staticmethod
    def _periodos(repo: ActividadesRepository) -> list[dict]:
        return list(repo.periods())

    @staticmethod
    def _huella_periodos(repo: ActividadesRepository) -> str:
        return _hash([_period(p) for p in repo.periods()])

    def _periodo_valido(self, scope: Scope, periodo_id: Any) -> int:
        pid = _id(periodo_id)
        ids = self._read(scope, lambda repo: {int(p["id"]) for p in repo.periods()})
        if pid not in ids:
            raise ActividadesError(404, "NOT_FOUND", MSG_PERIODO_NO_ENCONTRADO)
        return pid

    @staticmethod
    def _docentes_selector(repo: ActividadesRepository) -> list[dict]:
        """``get_docentes()`` efectiva (v281 off -> base v204): la base maestra del departamento, por import de Docentes
        (G2).  Las etiquetas v182/v183 no intervienen en el selector."""
        filas = DocentesRepository(repo._conn, repo.inst, repo.dep).docentes()
        return [{"etiqueta": AR.etiqueta_docente(r), "cuil": str(r.get("cuil") or "")} for r in filas]

    # ------------------------------------------------------------------ overview (encabezado l. 66419-66425)
    def overview(self, record: SessionRecord) -> dict:
        scope = self.reader(record)

        def read(repo: ActividadesRepository):
            abierto = repo.open_period()  # ``periodo_abierto`` (por defecto en los selectores de periodo)
            return {"periodos": [_period(p) for p in repo.periods()], "abierto": _period(abierto),
                    "huella_periodos": self._huella_periodos(repo)}
        data = self._read(scope, read)
        return {"contexto": {"institucion": _named(scope.institution), "departamento": _named(scope.department)},
                **data, "rol": scope.rol, "permisos": self._permisos(record), "estados": AR.ESTADOS,
                "info": INFO_PAGINA}

    # ------------------------------------------------------------------ Pestaña 1: actividades del periodo
    def actividades_periodo(self, record: SessionRecord, data: dict) -> dict:
        scope = self.reader(record)
        periodo_id = self._periodo_valido(scope, data.get("periodo_id"))

        def read(repo: ActividadesRepository):
            act = repo.actividades(periodo_id, incluir_inactivas=True)
            part = repo.participaciones_local(periodo_id=periodo_id, incluir_bajas=True) if not act.empty \
                else pd.DataFrame()
            return {"actividades": records(act.drop(columns=["id", "periodo_id"], errors="ignore")),
                    "participaciones": records(part, ["titulo", "docente", "cuil", "rol", "estado_asignacion",
                                                      "observaciones"]) if not part.empty else []}
        return self._read(scope, read)

    # ------------------------------------------------------------------ Pestaña 2: nueva actividad
    def crear(self, record: SessionRecord, data: dict) -> dict:
        scope = self.reader(record)
        periodo_id = self._periodo_valido(scope, data.get("periodo_id"))
        titulo, descripcion, obs = _text(data.get("titulo")), _text(data.get("descripcion")), _text(data.get("observaciones"))
        stale = self._stale(scope, data.get("huella_periodos"), self._huella_periodos, "get_periodos")
        self._op(record, scope, SPEC_GUARDAR, lambda u: E.guardar_actividad_especial(u, periodo_id, titulo, descripcion,
                                                                                     obs),
                 entity_raw=periodo_id, stale=stale)
        return {"mensaje": MSG_CREADA, "tono": "success"}

    # ------------------------------------------------------------------ Pestaña 3: asignar docentes
    def asignar_datos(self, record: SessionRecord, data: dict) -> dict:
        """Actividades ACTIVAS del periodo elegido y el selector de docentes (base maestra del departamento)."""
        scope = self.reader(record)
        periodo_id = self._periodo_valido(scope, data.get("periodo_id"))

        def read(repo: ActividadesRepository):
            act = repo.actividades(periodo_id, incluir_inactivas=False)
            docentes = self._docentes_selector(repo) if not act.empty else []
            return {"actividades": _con_huella(records(act), huella_actividad), "docentes": docentes}
        return self._read(scope, read)

    def asignar(self, record: SessionRecord, data: dict) -> dict:
        """"💾 Guardar participaciones" (l. 66513): N operaciones independientes; cada error se informa y el bucle
        sigue; una denegacion B10 corta (``st.error`` + ``st.stop()``)."""
        scope = self.reader(record)
        periodo_id = self._periodo_valido(scope, data.get("periodo_id"))
        actividad_id = _id(data.get("actividad_id"))
        docentes = data.get("docentes")
        if docentes in (None, ""):
            docentes = []
        if not isinstance(docentes, list):
            raise ActividadesError(422, "INVALID", MSG_VALOR_INVALIDO)

        def read(repo: ActividadesRepository):
            act = repo.actividades(periodo_id, incluir_inactivas=False)
            fila = act[pd.to_numeric(act.get("id", pd.Series(dtype=float)), errors="coerce").eq(actividad_id)] \
                if not act.empty else act
            return (fila.iloc[0].to_dict() if not fila.empty else None), self._docentes_selector(repo)
        actividad, selector = self._read(scope, read)
        if actividad is None or huella_actividad(actividad) != data.get("huella"):
            raise ActividadesError(409, "SELECCION", MSG_SELECCION_INVALIDA)
        validos = {o["cuil"] for o in selector}
        configs = []
        for d in docentes:
            if not isinstance(d, dict):
                raise ActividadesError(422, "INVALID", MSG_VALOR_INVALIDO)
            cuil = _text(d.get("cuil"))
            if cuil not in validos:
                raise ActividadesError(409, "SELECCION", MSG_SELECCION_INVALIDA)
            configs.append((cuil, _text(d.get("rol")), _text(d.get("observaciones"))))
        if not configs:
            raise ActividadesError(422, "VALIDATION", MSG_SIN_DOCENTES)
        if any(not str(rol or "").strip() for _, rol, _ in configs):
            raise ActividadesError(422, "VALIDATION", MSG_SIN_ROL)

        def fresh(repo: ActividadesRepository):
            act = repo.actividades(None, incluir_inactivas=True)
            fila = act[pd.to_numeric(act.get("id", pd.Series(dtype=float)), errors="coerce").eq(actividad_id)] \
                if not act.empty else act
            return huella_actividad(fila.iloc[0].to_dict() if not fila.empty else None)
        primera = {"stale": self._stale(scope, data.get("huella"), fresh, "get_actividades_especiales")}

        def tomar_stale():
            # El registro de lecturas B12I se vacia despues de cada writer: solo la primera operacion revalida.
            s, primera["stale"] = primera["stale"], None
            return s

        creadas, errores = 0, []
        for cuil, rol, obs in configs:
            try:
                self._op(record, scope, SPEC_ASIGNAR, lambda u: E.asignar_docente_actividad_especial(
                    u, actividad_id, cuil, rol, obs), entity_raw=actividad_id, stale=tomar_stale())
                creadas += 1
            except ActividadesError as exc:
                if exc.code == "DENIED":
                    raise
                errores.append(f"{cuil}: {exc.message}")
        return {"mensaje": f"Participaciones registradas: {creadas}." if creadas else "", "tono": "success",
                "avisos": errores}

    # ------------------------------------------------------------------ Pestaña 4: historial
    def historial(self, record: SessionRecord) -> dict:
        scope = self.reader(record)
        cols = ["periodo", "titulo", "docente", "cuil", "rol", "estado_actividad", "estado_asignacion", "observaciones",
                "fecha_carga"]
        return self._read(scope, lambda repo: {"filas": records(repo.participaciones_local(
            periodo_id=None, incluir_bajas=True), cols)})

    # ------------------------------------------------------------------ Pestaña 5: editar / eliminar
    def editar_datos(self, record: SessionRecord) -> dict:
        scope = self.reader(record)

        def read(repo: ActividadesRepository):
            filas = _con_huella(records(repo.actividades(None, incluir_inactivas=True)), huella_actividad)
            for f in filas:
                f["estado_mostrado"] = AR.estado_mostrado(f.get("estado"))
            return {"filas": filas, "estados": AR.ESTADOS}
        return self._read(scope, read)

    def participaciones_actividad(self, record: SessionRecord, data: dict) -> dict:
        """"Quitar una participación cargada por error" (l. 66573-66575): participaciones (con bajas) de esa actividad
        en su periodo."""
        scope = self.reader(record)
        actividad_id = _id(data.get("actividad_id"))
        actividad = self._actividad(scope, actividad_id)
        if actividad is None:
            raise ActividadesError(409, "SELECCION", MSG_SELECCION_INVALIDA)
        return {"filas": _con_huella(records(self._participaciones(scope, actividad)), huella_participacion)}

    def _actividad(self, scope: Scope, actividad_id: int) -> Optional[dict]:
        def read(repo: ActividadesRepository):
            act = repo.actividades(None, incluir_inactivas=True)
            fila = act[pd.to_numeric(act.get("id", pd.Series(dtype=float)), errors="coerce").eq(actividad_id)] \
                if not act.empty else act
            return fila.iloc[0].to_dict() if not fila.empty else None
        return self._read(scope, read)

    def _participaciones(self, scope: Scope, actividad: dict) -> pd.DataFrame:
        def read(repo: ActividadesRepository):
            df = repo.participaciones_local(periodo_id=int(actividad["periodo_id"]), incluir_bajas=True)
            if not df.empty:
                df = df[pd.to_numeric(df["actividad_id"], errors="coerce") == int(actividad["id"])].copy()
            return df
        return self._read(scope, read)

    def _actividad_vista(self, scope: Scope, data: dict) -> tuple[int, dict]:
        actividad_id = _id(data.get("actividad_id"))
        actividad = self._actividad(scope, actividad_id)
        if actividad is None or huella_actividad(actividad) != data.get("huella"):
            raise ActividadesError(409, "SELECCION", MSG_SELECCION_INVALIDA)
        return actividad_id, actividad

    def _stale_actividad(self, scope: Scope, actividad_id: int, huella: Any):
        def fresh(repo: ActividadesRepository):
            act = repo.actividades(None, incluir_inactivas=True)
            fila = act[pd.to_numeric(act.get("id", pd.Series(dtype=float)), errors="coerce").eq(actividad_id)] \
                if not act.empty else act
            return huella_actividad(fila.iloc[0].to_dict() if not fila.empty else None)
        return self._stale(scope, huella, fresh, "get_actividades_especiales")

    def editar(self, record: SessionRecord, data: dict) -> dict:
        scope = self.reader(record)
        actividad_id, _ = self._actividad_vista(scope, data)
        estado = _text(data.get("estado"))
        if estado not in AR.ESTADOS:
            raise ActividadesError(422, "INVALID", MSG_VALOR_INVALIDO)
        titulo, descripcion, obs = _text(data.get("titulo")), _text(data.get("descripcion")), _text(data.get("observaciones"))
        stale = self._stale_actividad(scope, actividad_id, data.get("huella"))
        self._op(record, scope, SPEC_ACTUALIZAR, lambda u: E.actualizar_actividad_especial(
            u, actividad_id, titulo, descripcion, estado, obs), entity_raw=actividad_id, stale=stale)
        return {"mensaje": MSG_ACTUALIZADA, "tono": "success"}

    def quitar_participacion(self, record: SessionRecord, data: dict) -> dict:
        scope = self.reader(record)
        actividad_id, actividad = self._actividad_vista(scope, data)
        if data.get("asignacion_id") in (None, ""):  # el boton certificado queda deshabilitado sin seleccion
            raise ActividadesError(422, "INVALID", MSG_VALOR_INVALIDO)
        aid = _id(data.get("asignacion_id"))
        filas = {int(r["id"]): huella_participacion(r) for r in records(self._participaciones(scope, actividad))}
        if filas.get(aid) is None or filas[aid] != data.get("huella_participacion"):
            raise ActividadesError(409, "SELECCION", MSG_SELECCION_INVALIDA)

        def fresh(repo: ActividadesRepository):
            df = repo.participaciones_local(periodo_id=int(actividad["periodo_id"]), incluir_bajas=True)
            fila = df[pd.to_numeric(df.get("id", pd.Series(dtype=float)), errors="coerce").eq(aid)] if not df.empty else df
            return huella_participacion(fila.iloc[0].to_dict() if not fila.empty else None)
        stale = self._stale(scope, filas[aid], fresh, "get_actividades_especiales_docente")
        self._op(record, scope, SPEC_ELIMINAR_ASIGNACION, lambda u: E.eliminar_asignacion_actividad_especial(u, aid),
                 entity_raw=aid, stale=stale)
        return {"mensaje": MSG_PARTICIPACION_ELIMINADA, "tono": "success"}

    def eliminar(self, record: SessionRecord, data: dict) -> dict:
        scope = self.reader(record)
        actividad_id, _ = self._actividad_vista(scope, data)
        if not _bool(data.get("confirmar")):
            raise ActividadesError(422, "VALIDATION", MSG_CONFIRMAR_ELIMINAR)
        stale = self._stale_actividad(scope, actividad_id, data.get("huella"))
        self._op(record, scope, SPEC_ELIMINAR, lambda u: E.eliminar_actividad_especial(u, actividad_id),
                 entity_raw=actividad_id, stale=stale)
        return {"mensaje": MSG_ELIMINADA, "tono": "success"}

    # ------------------------------------------------------------------ G5: lectura institucional (sin pantalla)
    def participaciones_docente_institucion(self, scope: Scope, cuil=None, periodo_id=None,
                                            incluir_bajas: bool = False) -> pd.DataFrame:
        """``get_actividades_especiales_docente(..., todos_departamentos=True)`` (l. 32126) para el futuro Resumen
        docente (Etapa 4).  Sin endpoint ni pantalla; no modifica Docentes."""
        return self._read(scope, lambda repo: repo.participaciones_institucion(cuil, periodo_id, incluir_bajas))


__all__ = ["ActividadesService", "ActividadesError", "huella_actividad", "huella_participacion"]
