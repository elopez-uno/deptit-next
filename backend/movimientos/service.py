"""Reglas de pantalla de Movimientos (B13-FIX02, ``elif modulo == "📜 Movimientos"`` l. 67764-67810).

Alcance (decisiones D-AL1..D-AL16, docs/movimientos_analysis.md §36): UNA pagina sin pestañas con el filtro de periodo,
el buscador, la tabla (primera fila seleccionada por defecto), la gestion masiva del acto administrativo de los
movimientos y "Eliminar movimiento del historial".  No existen (y no se agregan) alta, edicion, anulacion ni
regeneracion de movimientos, exportacion ni paginacion de servidor (D-AL9 / D-AL12).

Cada writer que la UI invoca es una operacion B12H propia (``correlation_id`` por writer):
1. comprobaciones de la pantalla (confirmacion, seleccion no vacia, formato): sin evento;
2. B10 del writer (``movimientos.delete`` -> solo superadmin; vincular ``documentos.write``; quitar vinculo
   ``documentos.delete`` -> solo superadmin): DENIED en transaccion propia;
3. B12I capa U (D-AL5): relectura fresca con el ambito de la sesion de las filas que el usuario vio; ids que ya no
   existen, de otro ambito o no seleccionables (D-AL4 / D-AL13) o con la huella cambiada -> FAILED sin escribir.
   Sin lock de capa T (ninguna familia);
4. su COMMIT certificado con SUCCESS (``commit_seq``); errores -> FAILED con ``coupled_commits``.
El ambito sale SIEMPRE de la sesion revalidada.  Ninguna lectura escribe (sin DDL ni reconciliaciones v207-v214,
D-AL14) y ninguna respuesta expone columnas legacy (``source_db``), rutas, SQL ni trazas (D-AL10).
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
from periodos.service import MSG_AUDIT_POST, MSG_DB_READ, MSG_DB_TRANSACTION, MSG_INSTITUTIONAL, MSG_STALE
from periodos.service import denial_message, scope_message

from . import escrituras as E
from . import rules as R
from .repository import COLUMNAS, MovimientosRepository

log = logging.getLogger("deptit_next.movimientos")

MODULO = "movimientos"
DEP = policy.SCOPE_DEPARTMENT
ACTION_READ = policy.Action("movimientos", policy.OP_READ, DEP)
ACTION_DELETE = policy.Action("movimientos", policy.OP_DELETE, DEP)
ACTION_DOC_WRITE = policy.Action("documentos", policy.OP_WRITE, DEP)
ACTION_DOC_DELETE = policy.Action("documentos", policy.OP_DELETE, DEP)


@dataclass(frozen=True)
class WriterSpec:
    """Writer del registro B10 (``legacy_write_actions.py``) y su etiqueta B12H
    (docs/audit/movimientos_phase_a/b10_b12h_movimientos.txt)."""
    name: str
    action: policy.Action
    entity_type: str
    entity_param: Optional[str]


# D-AL16: ``_entity_param`` certificado no reconoce ``id_movimiento`` -> ``entity_id`` NULL (rareza replicada).
SPEC_ELIMINAR = WriterSpec(E.W_ELIMINAR, ACTION_DELETE, "movimiento", None)
SPEC_VINCULAR = WriterSpec(E.W_VINCULAR_MASIVO, ACTION_DOC_WRITE, "acto_administrativo", "documento_id")
SPEC_DESVINCULAR = WriterSpec(E.W_DESVINCULAR_MASIVO, ACTION_DOC_DELETE, "acto_administrativo", None)

# Textos propios de la API (en Streamlit la seleccion sale siempre de la tabla en pantalla).
MSG_VALOR_INVALIDO = "Uno de los valores enviados no es válido para este formulario."
MSG_PERIODO_NO_ENCONTRADO = "El período seleccionado ya no existe. Actualizá la pantalla."
MSG_MOVIMIENTO_NO_ENCONTRADO = "No se encontró el movimiento seleccionado. Actualizá la pantalla."
MSG_SELECCION_INVALIDA = "La selección no corresponde a los movimientos mostrados. Actualizá la pantalla."
MSG_ACTO_SIN_SELECCION = "Seleccioná un acto administrativo del repositorio."
MSG_ACTO_NO_ENCONTRADO = "El acto administrativo seleccionado ya no está disponible en el repositorio."


class MovimientosError(Exception):
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


def _id(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise MovimientosError(422, "INVALID", MSG_VALOR_INVALIDO)
    return value


def _named(row: dict) -> dict:
    return {"id": int(row["id"]), "nombre": row.get("nombre")}


def _seleccion(data: dict) -> dict[int, str]:
    """``[{id, huella}, ...]`` no vacia (sin seleccion la pantalla certificada no muestra los botones)."""
    seleccion = data.get("seleccion")
    if not isinstance(seleccion, list) or not seleccion:
        raise MovimientosError(422, "INVALID", MSG_VALOR_INVALIDO)
    out: dict[int, str] = {}
    for item in seleccion:
        if not isinstance(item, dict) or not isinstance(item.get("huella"), str):
            raise MovimientosError(422, "INVALID", MSG_VALOR_INVALIDO)
        out[_id(item.get("id"))] = item["huella"]
    return out


def tabla(rows: list[dict], mapa: dict) -> list[dict]:
    """``_enriquecer_movimientos_acto_v266(get_movimientos(...))`` -> filas de la API (con ``huella``)."""
    df = pd.DataFrame(rows, columns=COLUMNAS)
    if df.empty:
        return []
    out = R.enriquecer(df, mapa)
    return [R.fila_api(r) for r in out.to_dict("records")]


def leer_tabla(repo: MovimientosRepository, periodo_id: Optional[int]) -> list[dict]:
    rows = repo.movimientos(periodo_id)
    return tabla(rows, _mapa(repo, rows))


def _mapa(repo: MovimientosRepository, rows: list[dict]) -> dict:
    """``_mapa_actos_movimientos_v266`` (SQL ya portado en Designaciones: ``actos_movimientos``)."""
    ids = sorted({int(r["id"]) for r in rows if r.get("id") is not None})
    if not ids:
        return {}
    return {int(a["movimiento_id"]): a for a in repo.actos_movimientos(ids)}


class MovimientosService:
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
            raise MovimientosError(409, "SCOPE_NOT_VERIFIED", scope_message(resolution))
        if not any(m[0] == MODULO for m in visible) or resolution.department is None:
            raise MovimientosError(409, "SCOPE_INSTITUTIONAL", MSG_INSTITUTIONAL)
        return Scope(int(resolution.institution["id"]), int(resolution.department["id"]), resolution.institution,
                     resolution.department)

    def reader(self, record: SessionRecord) -> Scope:
        scope = self.scope(record)
        actor = policy.actor_from_session(record.user, record.scope)
        decision = policy.decide(actor, ACTION_READ)
        if not decision.allowed:
            raise MovimientosError(403, "DENIED", denial_message(decision, ACTION_READ))
        return scope

    def _read(self, scope: Scope, fn: Callable[[MovimientosRepository], Any]) -> Any:
        try:
            with self._transaction() as conn:
                conn.execute("SET TRANSACTION READ ONLY")
                return fn(MovimientosRepository(conn, scope.institution_id, scope.department_id))
        except MovimientosError:
            raise
        except Exception as exc:
            log.error("movimientos: lectura fallida: %s", type(exc).__name__)
            raise MovimientosError(503, "DB_READ", MSG_DB_READ) from None

    @staticmethod
    def _permisos(record: SessionRecord) -> dict:
        """Solo UX (D-AL2): cada boton se muestra si B10 lo permitiria; la autoridad es B10 en cada writer."""
        actor = policy.actor_from_session(record.user, record.scope)
        return {"puede_eliminar": policy.decide(actor, ACTION_DELETE).allowed,
                "puede_vincular": policy.decide(actor, ACTION_DOC_WRITE).allowed,
                "puede_desvincular": policy.decide(actor, ACTION_DOC_DELETE).allowed}

    @staticmethod
    def _usuario(record: SessionRecord) -> str:
        """``_usuario_acto_v266``: email o nombre del usuario actual (``usuario_vinculacion``)."""
        return str(record.user.get("email") or record.user.get("nombre") or "").strip()

    # ------------------------------------------------------------------ B10 + B12I(U) + B12H por writer
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
        """Un writer certificado completo: B10 -> B12I capa U (``stale``) -> su COMMIT con SUCCESS, o FAILED."""
        actor = policy.actor_from_session(record.user, record.scope)
        audit_actor = audit.actor_from_record(record.user, record.scope, record.meta)
        op = audit.Operation(spec.name, spec.action, spec.entity_type, audit_actor, spec.entity_param, entity_raw)
        decision = policy.decide(actor, spec.action)
        if not decision.allowed:
            self._separate(op, audit.OUTCOME_DENIED, error_code=decision.code, metadata={"b10_decision": decision.code})
            raise MovimientosError(403, "DENIED", denial_message(decision, spec.action), "PermissionError")
        unidad = E.Unidad(self._transaction, op, scope.institution_id, scope.department_id, today=self.today(),
                          now=self.now(), usuario=self._usuario(record))

        def failed(error_code: str) -> None:
            self._separate(op, audit.OUTCOME_FAILED, error_code=error_code,
                           metadata={"coupled_commits": op.coupled_commits})
        try:
            if stale is not None:
                stale()
            result = fn(unidad)
        except MovimientosError as exc:
            failed(exc.error_class)
            raise
        except ValueError as exc:
            failed("ValueError")
            raise MovimientosError(422, "REJECTED", str(exc)) from None
        except E.AuditoriaFallida:
            failed("AuditPersistenceError:AUDIT_INSERT_FAILED")
            raise MovimientosError(503, "AUDIT", f"{audit.MSG_PERSIST} [AUDIT_INSERT_FAILED]",
                                   "AuditPersistenceError") from None
        except Exception as exc:
            log.error("movimientos: %s falló tras %d COMMIT(s): %s", spec.name, op.coupled_commits,
                      type(exc).__name__)
            failed(audit.error_code_of(exc))
            raise MovimientosError(503, "DB_ERROR", MSG_DB_TRANSACTION, type(exc).__name__) from None
        if op.coupled_commits == 0:
            if not self._separate(op, audit.OUTCOME_SUCCESS,
                                  metadata={"coupled_commits": 0, "post_reason": "NO_POOLED_COMMIT"}):
                raise MovimientosError(503, "AUDIT", MSG_AUDIT_POST)
        return result

    def _stale(self, scope: Scope, esperado: dict[int, str], *, seleccionables: bool,
               documento_id: Optional[int] = None) -> Callable[[], None]:
        """B12I capa U + seleccion fresca (D-AL4 / D-AL5 / D-AL13): cada id se relee con el ambito de la sesion."""
        def check() -> None:
            def read(repo: MovimientosRepository) -> dict:
                filas = {f["id"]: f for f in tabla(repo.movimientos_ids(sorted(esperado)),
                                                    _mapa(repo, [{"id": i} for i in esperado]))}
                docs = {int(d["id"]) for d in repo.documentos()} if documento_id is not None else set()
                return {"filas": filas, "docs": docs}
            try:
                fresh = self._read(scope, read)
            except MovimientosError:
                raise MovimientosError(503, "FRESH_READ", MSG_DB_READ, "FreshReadError") from None
            for mid in esperado:
                fila = fresh["filas"].get(mid)
                if fila is None:
                    if len(esperado) == 1 and not seleccionables:
                        raise MovimientosError(404, "NOT_FOUND", MSG_MOVIMIENTO_NO_ENCONTRADO, "LookupError")
                    raise MovimientosError(409, "SELECCION", MSG_SELECCION_INVALIDA, "LookupError")
                if seleccionables and not R.elegible_acto(fila.get("tipo_movimiento")):
                    raise MovimientosError(409, "SELECCION", MSG_SELECCION_INVALIDA, "LookupError")
            for mid, h in esperado.items():
                if fresh["filas"][mid]["huella"] != h:
                    raise MovimientosError(409, "STALE", f"{MSG_STALE} [B12I: get_movimientos]", "StaleDecisionError")
            if documento_id is not None and documento_id not in fresh["docs"]:
                raise MovimientosError(409, "ACTO_NO_ENCONTRADO", MSG_ACTO_NO_ENCONTRADO, "LookupError")
        return check

    # ------------------------------------------------------------------ lecturas de la pagina
    def overview(self, record: SessionRecord) -> dict:
        scope = self.reader(record)

        def read(repo: MovimientosRepository) -> dict:
            periodos = repo.periods()
            if not periodos:  # sin periodos: sin selector y todos los movimientos (l. 67769-67778)
                return {"opciones": [], "periodo": None, "filas": leer_tabla(repo, None)}
            opciones = R.opciones_periodos(periodos)
            inicial = R.periodo_inicial(opciones, repo.open_period(), repo.last_period())
            return {"opciones": list(opciones), "periodo": inicial, "filas": leer_tabla(repo, opciones[inicial])}

        d = self._read(scope, read)
        return {
            "contexto": {"institucion": _named(scope.institution), "departamento": _named(scope.department)},
            "periodos": d["opciones"], "periodo": d["periodo"], "filas": d["filas"],
            "tipos_con_acto": sorted(R.MOVIMIENTOS_ACTO_ADMINISTRATIVO_V266),
            "permisos": self._permisos(record),
        }

    def listado(self, record: SessionRecord, data: dict) -> dict:
        """Cambio del selector "Filtrar por período": la opcion se resuelve por NOMBRE contra ``get_periodos``."""
        scope = self.reader(record)
        etiqueta = data.get("periodo")
        if etiqueta is not None and not isinstance(etiqueta, str):
            raise MovimientosError(422, "INVALID", MSG_VALOR_INVALIDO)

        def read(repo: MovimientosRepository) -> dict:
            periodos = repo.periods()
            if not periodos:
                return {"periodo": None, "filas": leer_tabla(repo, None)}
            opciones = R.opciones_periodos(periodos)
            elegida = R.TODOS if etiqueta is None else etiqueta
            if elegida not in opciones:
                raise MovimientosError(409, "PERIODO", MSG_PERIODO_NO_ENCONTRADO)
            return {"periodo": elegida, "filas": leer_tabla(repo, opciones[elegida])}

        return self._read(scope, read)

    def actos(self, record: SessionRecord) -> dict:
        """Repositorio de Resoluciones y respaldos para el selector v266 (solo lectura; mismo SQL que Designaciones)."""
        scope = self.reader(record)
        docs = self._read(scope, lambda repo: repo.documentos())
        out = []
        for d in docs:
            row = {k: R._jsonable(d.get(k)) for k in ("id", "fecha", "tipo_documento", "numero", "dependencia_emisora",
                                                        "categoria", "titulo", "detalle", "periodo")}
            if row.get("fecha") is not None:
                row["fecha"] = str(row["fecha"])
            row["etiqueta"] = R.etiqueta_acto(d.get("tipo_documento"), d.get("numero"), d.get("dependencia_emisora"))
            out.append(row)
        return {"documentos": out}

    # ------------------------------------------------------------------ escrituras
    def eliminar(self, record: SessionRecord, data: dict) -> dict:
        """"🗑️ Eliminar movimiento" (l. 67800-67809): sin confirmacion no se llama al writer."""
        scope = self.scope(record)
        mid = _id(data.get("id"))
        h = data.get("huella")
        if not isinstance(h, str):
            raise MovimientosError(422, "INVALID", MSG_VALOR_INVALIDO)
        if data.get("confirmar") is not True:
            raise MovimientosError(422, "CONFIRMAR", R.MSG_CONFIRMAR)
        self._op(record, scope, SPEC_ELIMINAR, lambda u: E.eliminar_movimiento(u, mid),
                 stale=self._stale(scope, {mid: h}, seleccionables=False))
        return {"mensaje": R.MSG_ELIMINADO, "tono": "warning"}

    def vincular(self, record: SessionRecord, data: dict, quitar: bool) -> dict:
        """Botones del expander de actos (l. 55628-55639)."""
        scope = self.scope(record)
        esperado = _seleccion(data)
        ids = sorted(esperado)
        if quitar:
            n = self._op(record, scope, SPEC_DESVINCULAR, lambda u: E.desvincular_acto_movimientos_masivo(u, ids),
                         stale=self._stale(scope, esperado, seleccionables=True))
            return {"mensaje": f"Se quitaron {n} vínculo/s de movimiento.", "tono": "warning"}
        documento_id = data.get("documento_id")
        if documento_id is None:
            raise MovimientosError(422, "ACTO_SIN_SELECCION", MSG_ACTO_SIN_SELECCION)
        documento_id = _id(documento_id)
        n = self._op(record, scope, SPEC_VINCULAR,
                     lambda u: E.vincular_acto_movimientos_masivo(u, ids, documento_id), entity_raw=documento_id,
                     stale=self._stale(scope, esperado, seleccionables=True, documento_id=documento_id))
        return {"mensaje": f"Acto administrativo vinculado a {n} movimiento/s.", "tono": "success"}
