"""Administración SaaS (B13-FIX02 ``render_admin_saas`` l. 3339-3693; menú l. 52134; ruteo l. 59798).

Solo superadmin, re-autorizado en CADA request: lecturas con ``saas.read`` y writers con su acción certificada
(``saas.admin`` / ``saas.delete``, alcance global; ``legacy_write_actions.py`` l. 231-243).  Cualquier otro rol (incluido
el read_only comercial, que la sesión ya convierte en ``solo_lectura``) recibe 403.  SaaS es global por diseño: la
institución/departamento operativos de la sesión no limitan lo que administra, pero ningún id del cliente se usa sin
validarlo (entero estricto, existencia y relaciones) y cada acción tiene un esquema de campos explícito (sin mass
assignment: un campo extra -> 422 sin eco del valor).

Cada writer es una operación B12H (``audit.Operation``): DENIED/FAILED en transacción propia, SUCCESS en la misma
transacción del COMMIT único (``escrituras.Unidad``).  Los cambios de usuarios/instituciones revocan las sesiones
afectadas en su siguiente request por la revalidación B12G de Auth NEXT (sin tocar Auth).
"""

from __future__ import annotations

import logging
import math
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable, Optional

import pandas as pd
from psycopg import Connection

import audit
from analisis.pagina import tabla
from auth import core, policy
from auth.service import AuthService, SessionRecord
from inicio.service import XLSX, excel_bytes
from periodos.service import MSG_AUDIT_POST, MSG_DB_READ, MSG_DB_TRANSACTION, denial_message

from . import escrituras as E
from . import lecturas as L
from . import textos as T

log = logging.getLogger("deptit_next.saas")

GLOBAL = policy.SCOPE_GLOBAL
ACTION_READ = policy.Action(policy.DOMAIN_SAAS, policy.OP_READ, GLOBAL)
ACTION_ADMIN = policy.Action(policy.DOMAIN_SAAS, policy.OP_ADMIN, GLOBAL)
ACTION_DELETE = policy.Action(policy.DOMAIN_SAAS, policy.OP_DELETE, GLOBAL)
MODULO = "administracion_saas"
MSG_INVALIDO = "La solicitud no es válida."
MAX_TEXTO, MAX_NOMBRE, MAX_EMAIL, MAX_PASSWORD = 2000, 200, 320, 256


class SaasError(Exception):
    def __init__(self, status: int, code: str, message: str, error_class: str = "ValueError", tone: str = "error"):
        super().__init__(message)
        self.status, self.code, self.message, self.error_class, self.tone = status, code, message, error_class, tone


@dataclass(frozen=True)
class WriterSpec:
    """Writer del registro B10 y su etiqueta B12H (``entity_type_for``/``_entity_param`` certificados; D-AP7 en altas)."""
    name: str
    action: policy.Action
    entity_type: str
    entity_param: Optional[str]
    prefijo: str


SPECS = {
    E.W_CREAR_INSTITUCION: WriterSpec(E.W_CREAR_INSTITUCION, ACTION_ADMIN, "institucion", None, T.PREFIJO["crear"]),
    E.W_CUPO: WriterSpec(E.W_CUPO, ACTION_ADMIN, "institucion", "institucion_id", T.PREFIJO["actualizar"]),
    E.W_COMERCIAL: WriterSpec(E.W_COMERCIAL, ACTION_ADMIN, "institucion", "institucion_id", T.PREFIJO["actualizar"]),
    E.W_ESTADO_INSTITUCION: WriterSpec(E.W_ESTADO_INSTITUCION, ACTION_ADMIN, "institucion", "institucion_id",
                                       T.PREFIJO["actualizar"]),
    E.W_ELIMINAR_INSTITUCION: WriterSpec(E.W_ELIMINAR_INSTITUCION, ACTION_DELETE, "institucion", "institucion_id",
                                         T.PREFIJO["eliminar_inst"]),
    E.W_CREAR_DEPARTAMENTO: WriterSpec(E.W_CREAR_DEPARTAMENTO, ACTION_ADMIN, "departamento", None, T.PREFIJO["crear"]),
    E.W_ACTUALIZAR_DEPARTAMENTO: WriterSpec(E.W_ACTUALIZAR_DEPARTAMENTO, ACTION_ADMIN, "departamento",
                                            "departamento_id", T.PREFIJO["actualizar"]),
    E.W_ELIMINAR_DEPARTAMENTO: WriterSpec(E.W_ELIMINAR_DEPARTAMENTO, ACTION_DELETE, "departamento", "departamento_id",
                                          T.PREFIJO["eliminar"]),
    E.W_CREAR_USUARIO: WriterSpec(E.W_CREAR_USUARIO, ACTION_ADMIN, "usuario", None, T.PREFIJO["crear_usuario"]),
    E.W_ACTUALIZAR_USUARIO: WriterSpec(E.W_ACTUALIZAR_USUARIO, ACTION_ADMIN, "usuario", "usuario_id",
                                       T.PREFIJO["actualizar_usuario"]),
    E.W_ESTADO_USUARIO: WriterSpec(E.W_ESTADO_USUARIO, ACTION_ADMIN, "usuario", "usuario_id",
                                   T.PREFIJO["actualizar_usuario"]),
    E.W_ELIMINAR_USUARIO: WriterSpec(E.W_ELIMINAR_USUARIO, ACTION_DELETE, "usuario", "usuario_id",
                                     T.PREFIJO["eliminar_usuario"]),
}


# ------------------------------------------------------------------------------------------ esquemas por acción
def _entero(v: Any) -> int:
    if isinstance(v, bool) or not isinstance(v, int) or v <= 0 or v > 2**53:
        raise SaasError(422, "INVALID", MSG_INVALIDO)
    return v


def _entero_opcional(v: Any) -> Optional[int]:
    return None if v is None else _entero(v)


def _cupo(v: Any) -> int:
    if isinstance(v, bool) or not isinstance(v, int) or not T.CUPO_MIN <= v <= T.CUPO_MAX:
        raise SaasError(422, "INVALID", MSG_INVALIDO)
    return v


def _texto(v: Any, maximo: int = MAX_TEXTO) -> str:
    if v is None:
        return ""
    if not isinstance(v, str) or len(v) > maximo:
        raise SaasError(422, "INVALID", MSG_INVALIDO)
    return v


def _opcion(v: Any, catalogo: list[str]) -> str:
    if not isinstance(v, str) or v not in catalogo:
        raise SaasError(422, "INVALID", MSG_INVALIDO)
    return v


def _bool(v: Any) -> bool:
    if v is None:
        return False
    if not isinstance(v, bool):
        raise SaasError(422, "INVALID", MSG_INVALIDO)
    return v


def _fecha(v: Any) -> Optional[str]:
    if v is None or v == "":
        return None
    if not isinstance(v, str):
        raise SaasError(422, "INVALID", MSG_INVALIDO)
    try:
        return E.fecha_iso(v)
    except ValueError:
        raise SaasError(422, "INVALID", MSG_INVALIDO) from None


ESQUEMAS: dict[str, dict[str, Callable[[Any], Any]]] = {
    "planes": {"institucion_id": _entero},
    "excel": {"tabla": lambda v: _texto(v, 40), "id": _entero_opcional},
    "crear_institucion": {"nombre": lambda v: _texto(v, MAX_NOMBRE), "max_usuarios": _cupo,
                          "plan": lambda v: _opcion(v, T.PLANES_COMERCIALES), "fecha_vencimiento": _fecha,
                          "estado_pago": lambda v: _opcion(v, T.ESTADOS_PAGO),
                          "suscripcion": lambda v: _opcion(v, T.ESTADOS_SUSCRIPCION),
                          "estado": lambda v: _opcion(v, T.ESTADOS_INSTITUCION), "observaciones": _texto},
    "cupo": {"institucion_id": _entero, "max_usuarios": _cupo},
    "comercial": {"institucion_id": _entero, "plan": lambda v: _opcion(v, T.PLANES_COMERCIALES),
                  "max_usuarios": _cupo, "fecha_vencimiento": _fecha,
                  "estado_pago": lambda v: _opcion(v, T.ESTADOS_PAGO),
                  "suscripcion": lambda v: _opcion(v, T.ESTADOS_SUSCRIPCION),
                  "estado": lambda v: _opcion(v, T.ESTADOS_INSTITUCION), "observaciones": _texto},
    "institucion_id": {"institucion_id": _entero},
    "eliminar_institucion": {"institucion_id": _entero, "confirmado": _bool, "texto": lambda v: _texto(v, 40)},
    "crear_departamento": {"institucion_id": _entero, "nombre": lambda v: _texto(v, MAX_NOMBRE),
                           "observaciones": _texto},
    "editar_departamento": {"departamento_id": _entero, "nombre": lambda v: _texto(v, MAX_NOMBRE),
                            "estado": lambda v: _opcion(v, T.ESTADOS_DEPARTAMENTO), "observaciones": _texto},
    "eliminar_departamento": {"departamento_id": _entero, "confirmado": _bool},
    "crear_usuario": {"institucion_id": _entero, "departamento_id": _entero_opcional,
                      "nombre": lambda v: _texto(v, MAX_NOMBRE), "email": lambda v: _texto(v, MAX_EMAIL),
                      "rol": lambda v: _opcion(v, T.AUTH_ROLES), "password": lambda v: _texto(v, MAX_PASSWORD),
                      "password_confirmacion": lambda v: _texto(v, MAX_PASSWORD),
                      "estado": lambda v: _opcion(v, T.ESTADOS_USUARIO), "observaciones": _texto},
    "estado_usuario": {"usuario_id": _entero, "estado": lambda v: _opcion(v, T.ESTADOS_USUARIO)},
    "editar_usuario": {"usuario_id": _entero, "institucion_id": _entero_opcional,
                       "departamento_id": _entero_opcional, "nombre": lambda v: _texto(v, MAX_NOMBRE),
                       "email": lambda v: _texto(v, MAX_EMAIL), "rol": lambda v: _opcion(v, T.AUTH_ROLES),
                       "estado": lambda v: _opcion(v, T.ESTADOS_USUARIO), "observaciones": _texto,
                       "password": lambda v: _texto(v, MAX_PASSWORD)},
    "eliminar_usuario": {"usuario_id": _entero, "confirmado": _bool},
}


def validar(esquema: str, data: Any) -> dict:
    """Campos EXACTOS de la acción: ninguno extra (mass assignment), todos presentes, tipos estrictos."""
    campos = ESQUEMAS[esquema]
    if not isinstance(data, dict) or set(data) - set(campos):
        raise SaasError(422, "INVALID", MSG_INVALIDO)
    return {k: fn(data.get(k)) for k, fn in campos.items()}


# ------------------------------------------------------------------------------------------ serialización
def _celda(v: Any) -> Any:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    if hasattr(v, "item") and not isinstance(v, (str, bytes)):
        v = v.item()
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return v


def _filas(df: pd.DataFrame, columnas: list[str]) -> list[dict]:
    if df is None or df.empty:
        return []
    return [{c: _celda(r.get(c)) for c in columnas if c in df.columns} for r in df.to_dict("records")]


def _etiqueta_usuario(r: dict) -> str:
    """Opciones de los selectores certificados: ``"{email} - {rol} - {estado}"``."""
    return f"{r.get('email')} - {r.get('rol')} - {r.get('estado')}"


class SaasService:
    def __init__(self, pool, auth: AuthService, audit_store: audit.AuditStore, *,
                 today: Callable[[], date] = date.today, now: Callable[[], datetime] = datetime.now,
                 transaction: Optional[Callable[[], AbstractContextManager[Connection]]] = None):
        self.auth = auth
        self.audit_store = audit_store
        self.today = today
        self.now = now
        self._transaction = transaction or (lambda: pool.connection(timeout=5))

    # ------------------------------------------------------------------ autorización (cada request)
    def _lector(self, record: SessionRecord) -> None:
        actor = policy.actor_from_session(record.user, record.scope)
        visible = any(m[0] == MODULO for m in policy.visible_modules(policy.normalize_role(record.user.get("rol")),
                                                                     record.scope.get(policy.DEPARTMENT_SCOPE_KEY)))
        if not visible or not policy.decide(actor, ACTION_READ).allowed:
            raise SaasError(403, "DENIED", T.MSG_SOLO_SUPERADMIN, "PermissionError")

    def _read(self, fn: Callable[[Connection], Any]) -> Any:
        try:
            with self._transaction() as conn:
                conn.execute("SET TRANSACTION READ ONLY")
                return fn(conn)
        except SaasError:
            raise
        except Exception as exc:
            log.error("saas: lectura fallida: %s", type(exc).__name__)
            raise SaasError(503, "DB_READ", MSG_DB_READ) from None

    # ------------------------------------------------------------------ lectura inicial (las 5 pestañas)
    def overview(self, record: SessionRecord) -> dict:
        self._lector(record)

        def read(conn: Connection) -> dict:
            inst = L.instituciones(conn)
            deps = L.departamentos(conn)
            users = L.usuarios(conn)
            uso = L.uso(conn, self.today())
            dep_inst = L.dependencias_instituciones(conn)
            dep_dep = L.dependencias_departamentos(conn)
            activos = {int(i): L.activos_institucion(conn, int(i)) for i in inst["id"]} if not inst.empty else {}
            return {"inst": inst, "deps": deps, "users": users, "uso": uso, "dep_inst": dep_inst, "dep_dep": dep_dep,
                    "activos": activos}
        d = self._read(read)
        inst, deps, users = d["inst"], d["deps"], d["users"]
        instituciones = []
        for r in inst.to_dict("records"):
            iid = int(r["id"])
            resumen = L.resumen_dependencias(d["dep_inst"].get(iid, {}))
            instituciones.append({
                **{c: _celda(r.get(c)) for c in ("id", "nombre", "estado", "plan", "max_usuarios", "fecha_vencimiento",
                                                  "estado_pago", "suscripcion", "observaciones")},
                "activos": d["activos"].get(iid, 0), "dependencias": resumen,
                "eliminable": not d["dep_inst"].get(iid),
                "ficha": tabla(L.datos_actuales(r, L.COLUMNAS_DATOS_INSTITUCION))})
        departamentos = []
        for r in deps.to_dict("records"):
            did = int(r["id"])
            dep = d["dep_dep"].get(did, {})
            departamentos.append({
                **{c: _celda(r.get(c)) for c in ("id", "institucion_id", "institucion", "nombre", "estado",
                                                  "observaciones")},
                "usuarios": dep.get("app_usuarios", 0), "dependencias": L.resumen_dependencias(dep),
                "eliminable": not dep, "ficha": tabla(L.datos_actuales(r, L.COLUMNAS_DATOS_DEPARTAMENTO))})
        usuarios = [{**{c: _celda(r.get(c)) for c in ("id", "institucion_id", "departamento_id", "nombre", "email",
                                                       "rol", "estado", "observaciones")},
                     "etiqueta": _etiqueta_usuario(r), "ficha": tabla(L.datos_actuales(r, L.COLUMNAS_DATOS_USUARIO))}
                    for r in users.to_dict("records")]
        return {
            "ui": T.UI,
            "catalogos": {"roles": T.AUTH_ROLES, "planes": T.PLANES_COMERCIALES, "pagos": T.ESTADOS_PAGO,
                          "suscripciones": T.ESTADOS_SUSCRIPCION, "accesos": T.ESTADOS_INSTITUCION,
                          "estados_usuario": T.ESTADOS_USUARIO, "estados_departamento": T.ESTADOS_DEPARTAMENTO,
                          "sin_departamento": T.SIN_DEPARTAMENTO,
                          "cupo": {"min": T.CUPO_MIN, "max": T.CUPO_MAX, "default": T.CUPO_DEFAULT}},
            "actor_id": core.to_int_or_none(record.user.get("id")),
            "tablas": {"instituciones": tabla(L.vista_instituciones(inst)),
                       "departamentos": tabla(L.vista_departamentos(deps)),
                       "usuarios": tabla(users), "uso": tabla(d["uso"])},
            "instituciones": instituciones, "departamentos": departamentos, "usuarios": usuarios,
        }

    def planes(self, record: SessionRecord, data: dict) -> dict:
        """"Integridad de planes de estudio" de la institución elegida (D-AP3: solo las métricas)."""
        self._lector(record)
        iid = validar("planes", data)["institucion_id"]

        def read(conn: Connection) -> dict:
            if L.instituciones(conn).query("id == @iid").empty:
                raise SaasError(404, "NOT_FOUND", E.MSG_INSTITUCION_INEXISTENTE)
            return L.planes(conn, iid)
        p = self._read(read)
        return {"metricas": [{"label": "Carreras", "valor": str(p["carreras"])},
                             {"label": "Materias", "valor": str(p["materias"])},
                             {"label": "Estado", "valor": p["estado"]}],
                "aviso": None if p["estado"] == "OK" else T.UI["departamentos"]["planes"]["sin_planes"]}

    # ------------------------------------------------------------------ Excel global (8 tablas, D-AP6)
    def excel(self, record: SessionRecord, data: dict) -> tuple[bytes, str]:
        self._lector(record)
        v = validar("excel", data)
        clave, ident = v["tabla"], v["id"]
        fichas = {"institucion": ("instituciones", L.COLUMNAS_DATOS_INSTITUCION),
                  "comercial": ("instituciones", L.COLUMNAS_DATOS_INSTITUCION),
                  "departamento": ("departamentos", L.COLUMNAS_DATOS_DEPARTAMENTO),
                  "usuario": ("usuarios", L.COLUMNAS_DATOS_USUARIO)}
        if clave not in ("instituciones", "departamentos", "usuarios", "uso") and clave not in fichas:
            raise SaasError(422, "INVALID", MSG_INVALIDO)
        if (clave in fichas) != (ident is not None):
            raise SaasError(422, "INVALID", MSG_INVALIDO)

        def read(conn: Connection) -> pd.DataFrame:
            if clave == "instituciones":
                return L.vista_instituciones(L.instituciones(conn))
            if clave == "departamentos":
                return L.vista_departamentos(L.departamentos(conn))
            if clave == "usuarios":
                return L.usuarios(conn)
            if clave == "uso":
                return L.uso(conn, self.today())
            origen, columnas = fichas[clave]
            df = {"instituciones": L.instituciones, "departamentos": L.departamentos, "usuarios": L.usuarios}[origen](
                conn)
            fila = df[df["id"] == ident] if not df.empty else df
            if fila.empty:
                raise SaasError(404, "NOT_FOUND", "El registro seleccionado ya no existe.")
            return L.datos_actuales(fila.iloc[0].to_dict(), columnas)
        df = self._read(read)
        if df is None or df.empty:
            raise SaasError(409, "SIN_DATOS", "No hay datos para descargar.", tone="info")
        return excel_bytes(df), f"Administración_SaaS_{self.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

    # ------------------------------------------------------------------ writers (B10 -> validación -> COMMIT + B12H)
    def _separate(self, op: audit.Operation, outcome: str, *, error_code: Optional[str] = None,
                  metadata: Optional[dict] = None) -> bool:
        mode = audit.MODE_POST_OPERATION if outcome == audit.OUTCOME_SUCCESS else audit.MODE_SEPARATE
        try:
            self.audit_store.append_separate(op.event(outcome, mode, error_code=error_code, metadata=metadata))
            return True
        except Exception as exc:
            log.error("B12H: el evento %s de %s no pudo persistirse (%s)", outcome, op.name, audit.error_code_of(exc))
            return False

    def _op(self, record: SessionRecord, writer: str, fn: Callable[[E.Unidad], Any], entity_raw: Any = None,
            previo: Optional[Callable[[], None]] = None) -> Any:
        spec = SPECS[writer]
        actor = policy.actor_from_session(record.user, record.scope)
        audit_actor = audit.actor_from_record(record.user, record.scope, record.meta)
        op = audit.Operation(spec.name, spec.action, spec.entity_type, audit_actor, spec.entity_param, entity_raw)
        decision = policy.decide(actor, spec.action)
        if not decision.allowed:
            self._separate(op, audit.OUTCOME_DENIED, error_code=decision.code, metadata={"b10_decision": decision.code})
            raise SaasError(403, "DENIED", denial_message(decision, spec.action), "PermissionError")
        unidad = E.Unidad(self._transaction, op, today=self.today(), now=self.now(), actor_user_id=audit_actor.user_id)

        def failed(code: str) -> None:
            self._separate(op, audit.OUTCOME_FAILED, error_code=code, metadata={"coupled_commits": op.coupled_commits})
        try:
            if previo is not None:
                previo()
            result = fn(unidad)
        except SaasError as exc:
            failed(exc.error_class)
            raise
        except ValueError as exc:
            failed("ValueError")
            raise SaasError(422, "REJECTED", f"{spec.prefijo}: {exc}") from None
        except E.AuditoriaFallida:
            failed("AuditPersistenceError:AUDIT_INSERT_FAILED")
            raise SaasError(503, "AUDIT", f"{audit.MSG_PERSIST} [AUDIT_INSERT_FAILED]", "AuditPersistenceError") \
                from None
        except Exception as exc:
            log.error("saas: %s falló: %s", spec.name, type(exc).__name__)
            failed(audit.error_code_of(exc))
            raise SaasError(503, "DB_ERROR", MSG_DB_TRANSACTION, type(exc).__name__) from None
        if op.coupled_commits == 0 and not self._separate(
                op, audit.OUTCOME_SUCCESS, metadata={"coupled_commits": 0, "post_reason": "NO_POOLED_COMMIT"}):
            raise SaasError(503, "AUDIT", MSG_AUDIT_POST)
        return result

    def _autorizar(self, record: SessionRecord, writer: str) -> None:
        """B10 del writer ANTES de validar el payload: un rol no autorizado recibe 403 y queda su evento DENIED."""
        spec = SPECS[writer]
        decision = policy.decide(policy.actor_from_session(record.user, record.scope), spec.action)
        if not decision.allowed:
            op = audit.Operation(spec.name, spec.action, spec.entity_type,
                                 audit.actor_from_record(record.user, record.scope, record.meta))
            self._separate(op, audit.OUTCOME_DENIED, error_code=decision.code, metadata={"b10_decision": decision.code})
            raise SaasError(403, "DENIED", denial_message(decision, spec.action), "PermissionError")

    @staticmethod
    def _ok(mensaje: str, tono: str = "success", **extra) -> dict:
        return {"mensaje": mensaje, "tono": tono, **extra}

    def _sesiones(self, pred: Callable[[SessionRecord], bool]) -> int:
        """Sesiones activas del almacén de Auth NEXT que cumplen ``pred`` (solo lectura; Auth no se modifica)."""
        store = self.auth.store
        with store._lock:
            records = list(store._items.values())
        return sum(1 for r in records if pred(r))

    # --- Instituciones
    def crear_institucion(self, record: SessionRecord, data: dict) -> dict:
        self._autorizar(record, E.W_CREAR_INSTITUCION)
        v = validar("crear_institucion", data)
        nid = self._op(record, E.W_CREAR_INSTITUCION, lambda u: E.crear_institucion_auth(
            u, v["nombre"], v["max_usuarios"], v["plan"], v["observaciones"], v["fecha_vencimiento"],
            v["estado_pago"], v["suscripcion"], v["estado"]))
        return self._ok(T.MSG["inst_creada"], id=nid)

    def actualizar_cupo(self, record: SessionRecord, data: dict) -> dict:
        self._autorizar(record, E.W_CUPO)
        v = validar("cupo", data)
        self._op(record, E.W_CUPO, lambda u: E.actualizar_cupo_institucion(u, v["institucion_id"], v["max_usuarios"]),
                 v["institucion_id"])
        return self._ok(T.MSG["cupo_actualizado"])

    def actualizar_comercial(self, record: SessionRecord, data: dict) -> dict:
        self._autorizar(record, E.W_COMERCIAL)
        v = validar("comercial", data)
        self._op(record, E.W_COMERCIAL, lambda u: E.actualizar_comercial_institucion(
            u, v["institucion_id"], v["plan"], v["max_usuarios"], v["fecha_vencimiento"], v["estado_pago"],
            v["suscripcion"], v["estado"], v["observaciones"]), v["institucion_id"])
        return self._ok(T.MSG["comercial_actualizado"])

    def bloquear(self, record: SessionRecord, data: dict) -> dict:
        self._autorizar(record, E.W_ESTADO_INSTITUCION)
        iid = validar("institucion_id", data)["institucion_id"]
        self._op(record, E.W_ESTADO_INSTITUCION, lambda u: E.cambiar_estado_institucion_auth(u, iid, "Bloqueada"), iid)
        return self._ok(T.MSG["inst_bloqueada"], "warning")

    def desbloquear(self, record: SessionRecord, data: dict) -> dict:
        self._autorizar(record, E.W_ESTADO_INSTITUCION)
        iid = validar("institucion_id", data)["institucion_id"]
        self._op(record, E.W_ESTADO_INSTITUCION, lambda u: E.cambiar_estado_institucion_auth(u, iid, "Activa"), iid)
        return self._ok(T.MSG["inst_activa"])

    def eliminar_institucion(self, record: SessionRecord, data: dict) -> dict:
        self._autorizar(record, E.W_ELIMINAR_INSTITUCION)
        v = validar("eliminar_institucion", data)
        if not v["confirmado"] or v["texto"].strip().upper() != "ELIMINAR":
            raise SaasError(422, "CONFIRMATION_REQUIRED", T.MSG_CONFIRMAR_INST)
        iid = v["institucion_id"]

        def operativa(r: SessionRecord) -> bool:
            return core.to_int_or_none(r.scope.get(policy.SUPERADMIN_INSTITUTION_KEY)) == iid or \
                core.to_int_or_none(r.user.get("institucion_id")) == iid
        self._op(record, E.W_ELIMINAR_INSTITUCION,
                 lambda u: E.eliminar_institucion_auth(u, iid, lambda: self._sesiones(operativa)), iid)
        return self._ok(T.MSG["inst_eliminada"], "warning")

    # --- Departamentos
    def crear_departamento(self, record: SessionRecord, data: dict) -> dict:
        self._autorizar(record, E.W_CREAR_DEPARTAMENTO)
        v = validar("crear_departamento", data)
        nid = self._op(record, E.W_CREAR_DEPARTAMENTO, lambda u: E.crear_departamento_auth(
            u, v["institucion_id"], v["nombre"], v["observaciones"]))
        return self._ok(T.MSG["dep_creado"], id=nid)

    def editar_departamento(self, record: SessionRecord, data: dict) -> dict:
        self._autorizar(record, E.W_ACTUALIZAR_DEPARTAMENTO)
        v = validar("editar_departamento", data)
        self._op(record, E.W_ACTUALIZAR_DEPARTAMENTO, lambda u: E.actualizar_departamento_auth(
            u, v["departamento_id"], v["nombre"], v["estado"], v["observaciones"]), v["departamento_id"])
        return self._ok(T.MSG["dep_actualizado"])

    def eliminar_departamento(self, record: SessionRecord, data: dict) -> dict:
        self._autorizar(record, E.W_ELIMINAR_DEPARTAMENTO)
        v = validar("eliminar_departamento", data)
        if not v["confirmado"]:
            raise SaasError(422, "CONFIRMATION_REQUIRED", T.MSG_CONFIRMAR)
        did = v["departamento_id"]

        def operativo(r: SessionRecord) -> bool:
            return core.to_int_or_none(r.scope.get(policy.DEPARTMENT_SCOPE_KEY)) == did or \
                core.to_int_or_none(r.user.get("departamento_id")) == did
        self._op(record, E.W_ELIMINAR_DEPARTAMENTO,
                 lambda u: E.eliminar_departamento_auth(u, did, lambda: self._sesiones(operativo)), did)
        return self._ok(T.MSG["dep_eliminado"], "warning")

    # --- Usuarios
    def crear_usuario(self, record: SessionRecord, data: dict) -> dict:
        self._autorizar(record, E.W_CREAR_USUARIO)
        v = validar("crear_usuario", data)
        if v["password"] != v["password_confirmacion"]:
            raise SaasError(422, "PASSWORDS", T.MSG_PASSWORDS_DISTINTAS)
        nid = self._op(record, E.W_CREAR_USUARIO, lambda u: E.crear_usuario_auth(
            u, v["institucion_id"], v["departamento_id"], v["nombre"], v["email"], v["rol"], v["password"],
            v["estado"], v["observaciones"]))
        return self._ok(T.MSG["usuario_creado"], id=nid)

    def estado_usuario(self, record: SessionRecord, data: dict) -> dict:
        self._autorizar(record, E.W_ESTADO_USUARIO)
        v = validar("estado_usuario", data)
        self._op(record, E.W_ESTADO_USUARIO, lambda u: E.cambiar_estado_usuario_auth(u, v["usuario_id"], v["estado"]),
                 v["usuario_id"])
        return self._ok(T.MSG["estado_actualizado"])

    def editar_usuario(self, record: SessionRecord, data: dict) -> dict:
        self._autorizar(record, E.W_ACTUALIZAR_USUARIO)
        v = validar("editar_usuario", data)
        self._op(record, E.W_ACTUALIZAR_USUARIO, lambda u: E.actualizar_usuario_auth(
            u, v["usuario_id"], v["institucion_id"], v["departamento_id"], v["nombre"], v["email"], v["rol"],
            v["estado"], v["observaciones"], v["password"]), v["usuario_id"])
        return self._ok(T.MSG["usuario_actualizado"])

    def eliminar_usuario(self, record: SessionRecord, data: dict) -> dict:
        self._autorizar(record, E.W_ELIMINAR_USUARIO)
        v = validar("eliminar_usuario", data)
        if not v["confirmado"]:
            raise SaasError(422, "CONFIRMATION_REQUIRED", T.MSG_CONFIRMAR)
        self._op(record, E.W_ELIMINAR_USUARIO, lambda u: E.eliminar_usuario_auth(u, v["usuario_id"]), v["usuario_id"])
        return self._ok(T.MSG["usuario_eliminado"], "warning")
