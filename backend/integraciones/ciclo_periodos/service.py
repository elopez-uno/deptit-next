"""E4-10 / E4-11 / E4-12 — operaciones propias de Periodos, cada una en UNA transaccion (D-E4-06).

- **E4-10 Crear periodo** (entry l. 62685-63030 -> ``_crear_periodo_control_v310`` legacy -> ``crear_periodo``): B10
  ``periodos.write`` -> B11 gate de backup (D-E4-04, ``backup_gate.py``) -> B12C ``crear_periodo_atomico`` LITERAL
  (``motor/ref/b12c/periodo_atomico.py``) con la cascada certificada LITERAL (``motor/complemento.py``): S0 lock,
  S1 duplicado, S2 anterior, S3 cierre + alta, S4 movimiento de apertura, S5 vencimientos v268, S6 copia v266 (+
  vinculos documentales bajo SAVEPOINT), S7 investigacion, S8 extension, S9 finalizacion del anterior.  B12H SUCCESS
  en la misma transaccion; cualquier fallo -> ROLLBACK total y FAILED.
- **E4-11 Revertir ultimo cierre** (entry l. 63184-63247, ``diagnosticar_reversion_ultimo_cierre`` /
  ``revertir_ultimo_cierre_periodo`` LITERALES): superadmin; PREFLIGHT completo D-E4-05 (``inventario.py``): si el
  periodo nuevo tiene cualquier dato que la reversion certificada no borra, o filas que la reversion borraria tienen
  vinculos (FK, incluidas las ON DELETE CASCADE), NO se escribe nada y se rechaza con un mensaje funcional.  Si es
  reversible: el alcance certificado (reactivar cierres automaticos, borrar designaciones / movimientos / estado de
  consulta del periodo nuevo y el periodo, reabrir el anterior, movimiento "Reversión de cierre de período") en UNA
  transaccion (el certificado hacia 2 COMMITs).
- **E4-12 Eliminar periodo — NEXT solo vacio** (D-E4-03, P-12): ``eliminar_periodo_con_datos_admin`` NO se porta.
  Solo un periodo REALMENTE vacio (inventario explicito + dinamico) cuyo unico movimiento eventual es la apertura
  automatica identificada estructuralmente; sin cascada, sin borrar historia de otros periodos (si la creacion de
  este periodo cerro designaciones del anterior, se rechaza: corresponde Revertir).  Una transaccion: preflight ->
  borrar apertura -> borrar periodo -> reabrir el ultimo restante si era el abierto (como ``eliminar_periodo``
  certificado) -> movimiento "Eliminación de período vacío" -> B12H -> COMMIT.
- **E4-12 / P-12b Reparar finalizaciones automaticas del periodo abierto** (entry l. 63264-63284,
  ``diagnosticar_finalizaciones_automaticas_periodo`` / ``reactivar_finalizaciones_automaticas_periodo`` LITERALES;
  decision del usuario 2026-10-31: se porta dentro de E4-12).  Operacion PROPIA, separada de Eliminar: no borra
  periodos.  Superadmin + B10 ``periodos.write``.  PREFLIGHT NEXT fail closed: solo si el abierto es el ULTIMO periodo
  del ambito (si hay uno posterior, sus cierres son vigentes: el certificado los "repararia" igual) y cada movimiento de
  cierre corresponde exactamente a designaciones finalizadas del mismo CUIL y texto, sin vinculos y sin diferencias con
  la deteccion certificada (que tiene un fallback por CUIL unico).  Una transaccion: preflight -> writer certificado
  (reactivar + borrar los movimientos de cierre) -> verificacion -> B12H -> COMMIT.
Todas: ambito de la sesion revalidada; lock ``deptit_crear_periodo:{inst}:{dep}`` (el mismo de B12C y de B12I
"periodo_estado") dentro de la transaccion con espera acotada; respuesta con ``periodo_cambiado`` (P-01b).
"""
from __future__ import annotations

import hashlib
import json
import logging
from contextlib import AbstractContextManager
from datetime import date, datetime
from typing import Any, Callable, Optional

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row

import audit
from auth import core, policy
from auth.service import SessionRecord
from periodos.repository import PeriodosRepository
from periodos.service import (
    MSG_DB_READ, MSG_DB_TRANSACTION, MSG_LOCK, MSG_STALE, PeriodosError, PeriodosService, denial_message,
)

from . import backup_gate, entorno, inventario

log = logging.getLogger("deptit_next.integraciones")

ACTION_WRITE = policy.Action("periodos", policy.OP_WRITE, policy.SCOPE_DEPARTMENT)
ACTION_DELETE = policy.Action("periodos", policy.OP_DELETE, policy.SCOPE_DEPARTMENT)
LOCK_KEY = "deptit_crear_periodo:{inst}:{dep}"
LOCK_TIMEOUT = "30s"

# --- textos certificados (entry l. 62686-62706, 63185-63247)
AVISO_CREAR = ("Al crear un período nuevo, cualquier período abierto anterior quedará cerrado. Las designaciones "
               "concursadas que sigan vigentes se incorporarán automáticamente con sus fechas originales. La opción "
               "inferior controla únicamente la renovación de designaciones no concursadas del período anterior.")
MSG_CREADO = "Período creado correctamente."
ANIO_MIN, ANIO_MAX = 2020, 2100
INFO_REVERTIR = ("Esta opción sirve para deshacer el último cierre realizado por error. Elimina el período nuevo creado "
                 "por el cierre, borra sus renovaciones automáticas, reabre el período anterior y reactiva solo las "
                 "designaciones que fueron finalizadas automáticamente.")
MSG_SOLO_SUPERADMIN_REVERTIR = "Solo el superadmin puede revertir un cierre de período."
MSG_REVERTIR_CONFIRMAR = "Tenés que marcar las tres confirmaciones antes de revertir el cierre."
PREFIX_REVERTIR = "No se pudo revertir el cierre: "
# --- textos NEXT (D-E4-05, D-E4-03)
MSG_REVERTIR_DEPENDENCIAS = ("No se puede revertir el último cierre: el período {nombre} ya contiene información que la "
                             "reversión no elimina ({lista}). No se realizó ningún cambio.")
MSG_SIN_ANTERIOR = "No hay período anterior para restaurar."
MSG_ANTERIOR_AJENO = ("No se puede revertir el último cierre: el período anterior que calcula el sistema certificado no "
                      "pertenece a este departamento (anomalía de ámbito documentada). No se realizó ningún cambio.")
MSG_SOLO_SUPERADMIN_ELIMINAR = "Solo el superadmin puede eliminar períodos."
MSG_CON_DATOS = "El período contiene información y no puede eliminarse."
MSG_ELIMINAR_CONFIRMAR = "Tenés que marcar la confirmación antes de eliminar el período."
MSG_ELIMINAR_TEXTO = "La confirmación escrita no coincide. Escribí: {esperado}"
PREFIX_ELIMINAR = "No se pudo eliminar el período: "
INFO_ELIMINAR = ("Solo se puede eliminar un período realmente vacío, creado por error: sin designaciones, comisiones, "
                 "inscriptos, investigación, extensión, actividades especiales, disposiciones, estados de consulta, "
                 "documentos ni otros datos, y cuyo único movimiento sea la apertura automática del sistema. Un "
                 "período con cualquier información no se elimina (no se borra historia). Para deshacer un cierre, "
                 "usá Revertir último cierre.")
MSG_PERIODO_INVALIDO = "El período seleccionado no es válido."
MSG_PERIODO_NO_ENCONTRADO = "No se encontró el período seleccionado."
MSG_VALOR_INVALIDO = "Uno de los valores enviados no es válido para este formulario."
# --- P-12b: textos certificados (entry l. 63271-63284) y NEXT (preflight fail closed)
AVISO_REPARAR = ("El período abierto {nombre} todavía tiene finalizaciones automáticas por cierre. Se pueden reactivar "
                 "{designaciones} designación/es y limpiar {movimientos} movimiento/s automático/s.")
BOTON_REPARAR = "♻️ Reparar finalizaciones automáticas del período abierto"
MSG_REPARADO = ("Reparación realizada: {designaciones} designación/es reactivada/s y {movimientos} movimiento/s "
                "automático/s eliminado/s.")
PREFIX_REPARAR = "No se pudo reparar el período abierto: "
MSG_SOLO_SUPERADMIN_REPARAR = "Solo el superadmin puede reparar finalizaciones automáticas."
MSG_NADA_REPARAR = ("El período abierto no tiene finalizaciones automáticas por cierre para reparar. No se realizó "
                    "ningún cambio.")
MSG_REPARAR_BLOQUEADO = ("El período abierto {nombre} tiene {movimientos} finalización/es automática/s por cierre que no "
                         "se pueden reparar con seguridad ({lista}). No se realizará ningún cambio.")


def _jsonable(v: Any) -> Any:
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if hasattr(v, "item"):
        return v.item()
    if isinstance(v, float) and v != v:
        return None
    return v


def _period(row: Optional[dict]) -> Optional[dict]:
    if row is None:
        return None
    return {k: _jsonable(row.get(k)) for k in ("id", "nombre", "anio", "semestre", "fecha_inicio", "fecha_fin", "estado",
                                               "observaciones")}


def _huella(valor: Any) -> str:
    return hashlib.sha256(json.dumps(valor, sort_keys=True, default=str).encode()).hexdigest()


class CicloPeriodosService:
    def __init__(self, pool, periodos: PeriodosService, audit_store: audit.AuditStore, *, database_url: str = "",
                 today: Callable[[], date] = date.today, now: Callable[[], datetime] = datetime.now,
                 transaction: Optional[Callable[[], AbstractContextManager[Connection]]] = None,
                 env: Optional[dict] = None, evidencia: Optional[Callable] = None):
        self.periodos, self.audit_store = periodos, audit_store
        self.database_url = database_url
        self.today, self.now = today, now
        self._transaction = transaction or (lambda: pool.connection(timeout=5))
        self.env, self.evidencia = env, evidencia
        self.gate = backup_gate.configuracion(env)  # configuracion insegura -> el servicio no se construye
        self.lock_timeout = LOCK_TIMEOUT

    # ------------------------------------------------------------------ comunes
    def _actor(self, record: SessionRecord):
        return policy.actor_from_session(record.user, record.scope)

    def _es_superadmin(self, record: SessionRecord) -> bool:
        return policy.normalize_role(record.user.get("rol")) == policy.ROLE_SUPERADMIN

    def _op(self, record: SessionRecord, name: str, action: policy.Action, entity_param=None, entity_raw=None):
        audit_actor = audit.actor_from_record(record.user, record.scope, record.meta)
        op = audit.Operation(name, action, "periodo", audit_actor, entity_param, entity_raw)
        decision = policy.decide(self._actor(record), action)
        if not decision.allowed:
            self._separate(op, audit.OUTCOME_DENIED, error_code=decision.code, metadata={"b10_decision": decision.code})
            raise PeriodosError(403, "DENIED", denial_message(decision, action), "PermissionError")
        return op

    def _separate(self, op, outcome, *, error_code=None, metadata=None) -> None:
        try:
            self.audit_store.append_separate(op.event(outcome, audit.MODE_SEPARATE, error_code=error_code,
                                                      metadata=metadata))
        except Exception as exc:
            log.error("B12H: el evento %s de %s no pudo persistirse (%s)", outcome, op.name, audit.error_code_of(exc))

    def _ns(self, record: SessionRecord, scope) -> dict:
        usuario = {"email": record.user.get("email"), "rol": record.user.get("rol"), "nombre": record.user.get("nombre"),
                   "departamento_nombre": record.user.get("departamento_nombre") or ""}
        return entorno.construir(scope.institution_id, scope.department_id, usuario=usuario, hoy=self.today,
                                 ahora=self.now)

    def _lock(self, conn: Connection, scope) -> None:
        conn.execute(f"SET LOCAL lock_timeout = '{self.lock_timeout}'")
        conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))",
                     [LOCK_KEY.format(inst=scope.institution_id, dep=scope.department_id)])

    def _ejecutar(self, op, prefix: str, fn: Callable[[Connection], Any]) -> Any:
        """UNA transaccion: ``fn`` + SUCCESS B12H en ella; error -> ROLLBACK total + FAILED (sin efectos)."""
        try:
            with self._transaction() as conn:
                resultado, mutaciones, meta = fn(conn)
                try:
                    audit.insert_on(conn, op.event(audit.OUTCOME_SUCCESS, audit.MODE_IN_TRANSACTION, metadata={
                        "commit_seq": 1, "mutating_statements": mutaciones, "committing_writer": op.name, **meta}))
                except Exception as exc:
                    log.error("B12H: SUCCESS de %s no insertado (%s): ROLLBACK", op.name, audit.error_code_of(exc))
                    raise PeriodosError(503, "AUDIT", f"{audit.MSG_PERSIST} [AUDIT_INSERT_FAILED]",
                                        "AuditPersistenceError:AUDIT_INSERT_FAILED") from None
            return resultado
        except PeriodosError as exc:
            self._separate(op, audit.OUTCOME_FAILED, error_code=exc.error_class, metadata={"coupled_commits": 0})
            raise PeriodosError(exc.status, exc.code, prefix + exc.message, exc.error_class) from None
        except psycopg.errors.LockNotAvailable:
            self._separate(op, audit.OUTCOME_FAILED, error_code="ConsistencyLockError", metadata={"coupled_commits": 0})
            raise PeriodosError(409, "LOCK", prefix + f"{MSG_LOCK} [B12I: periodo_estado]", "ConsistencyLockError") \
                from None
        except Exception as exc:
            if type(exc).__name__ == "PeriodoDuplicadoError":
                self._separate(op, audit.OUTCOME_FAILED, error_code="PeriodoDuplicadoError",
                               metadata={"coupled_commits": 0})
                raise PeriodosError(409, "DUPLICADO", str(exc), "PeriodoDuplicadoError") from None
            log.error("ciclo_periodos: %s falló: %s", op.name, type(exc).__name__)
            self._separate(op, audit.OUTCOME_FAILED, error_code=audit.error_code_of(exc), metadata={"coupled_commits": 0})
            raise PeriodosError(503, "DB_ERROR", prefix + MSG_DB_TRANSACTION) from None

    def _leer(self, fn: Callable[[Connection], Any]) -> Any:
        try:
            with self._transaction() as conn:
                conn.execute("SET TRANSACTION READ ONLY")
                return fn(conn)
        except PeriodosError:
            raise
        except Exception as exc:
            log.error("ciclo_periodos: lectura fallida: %s", type(exc).__name__)
            raise PeriodosError(503, "DB_READ", MSG_DB_READ) from None

    # ------------------------------------------------------------------ E4-10 Crear periodo
    @staticmethod
    def _nombre_fechas(anio: int, semestre: int) -> tuple[str, str, str]:
        from analisis.motor.ref.extracted_batch01.periodos import nombre_periodo
        from analisis.motor.ref.extracted_batch04.fechas import fechas_periodo
        fi, ff = fechas_periodo(anio, semestre)
        return nombre_periodo(anio, semestre), fi, ff

    @staticmethod
    def _anio_semestre(data: dict) -> tuple[int, int]:
        anio, semestre = data.get("anio"), data.get("semestre")
        if isinstance(anio, bool) or not isinstance(anio, int) or not ANIO_MIN <= anio <= ANIO_MAX \
                or isinstance(semestre, bool) or semestre not in (1, 2):
            raise PeriodosError(422, "INVALID", MSG_VALOR_INVALIDO)
        return anio, semestre

    def crear_contexto(self, record: SessionRecord, data: dict) -> dict:
        """Pantalla "➕ Crear nuevo período": textos, periodo objetivo, duplicado (``get_periodo_por_nombre``) y gate."""
        scope = self.periodos.scope(record)
        data = data if isinstance(data, dict) else {}
        anio = data.get("anio", self.today().year)
        semestre = data.get("semestre", 1)
        anio, semestre = self._anio_semestre({"anio": anio, "semestre": semestre})
        nombre, fi, ff = self._nombre_fechas(anio, semestre)

        def read(conn):
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT id, nombre, anio, semestre, fecha_inicio, fecha_fin, estado, observaciones FROM "
                            "periodos WHERE nombre = %s AND institucion_id = %s AND departamento_id = %s LIMIT 1",
                            [nombre.strip(), scope.institution_id, scope.department_id])
                return cur.fetchone()
        existente = self._leer(read)
        return {"aviso": AVISO_CREAR, "anio_min": ANIO_MIN, "anio_max": ANIO_MAX, "anio_default": self.today().year,
                "semestres": [{"valor": 1, "etiqueta": "1° período: 01/01 al 31/07"},
                              {"valor": 2, "etiqueta": "2° período: 01/08 al 31/12"}],
                "objetivo": {"nombre": nombre, "fecha_inicio": fi, "fecha_fin": ff},
                "existente": _period(existente),
                "gate": {"activo": self.gate.activo, "entorno": self.gate.entorno,
                         "aviso": None if self.gate.activo else backup_gate.AVISO_DESACTIVADO},
                "puede_escribir": policy.decide(self._actor(record), ACTION_WRITE).allowed}

    def crear(self, record: SessionRecord, data: dict) -> dict:
        scope = self.periodos.scope(record)
        data = data if isinstance(data, dict) else {}
        anio, semestre = self._anio_semestre(data)
        copiar = data.get("copiar_anterior", True)
        observaciones = data.get("observaciones", "")
        if not isinstance(copiar, bool) or not isinstance(observaciones, str):
            raise PeriodosError(422, "INVALID", MSG_VALOR_INVALIDO)
        op = self._op(record, "crear_periodo", ACTION_WRITE, "anio", anio)
        decision = backup_gate.evaluar(self.database_url, env=self.env, evidencia=self.evidencia)
        if not decision.permitido:  # B11: antes de abrir la transaccion (0 SQL)
            self._separate(op, audit.OUTCOME_FAILED, error_code="BackupPreconditionError",
                           metadata={"coupled_commits": 0})
            raise PeriodosError(409, "BACKUP", decision.mensaje, "BackupPreconditionError")
        ns = self._ns(record, scope)
        trazas: dict = {}

        def body(conn: Connection):
            conn.execute(f"SET LOCAL lock_timeout = '{self.lock_timeout}'")
            pid = entorno.B12C.crear_periodo_atomico(ns, lambda: entorno.RawTx(conn),
                                                     lambda t: trazas.__setitem__("t", t), anio, semestre, copiar,
                                                     observaciones)
            t = trazas["t"]
            if t.outcome != "committed":
                raise entorno.B12C.TransactionAborted(f"crear_periodo no confirmó: {t.outcome}")
            return int(pid), len(t.writes), {}

        pid = self._ejecutar(op, "", body)
        t = trazas["t"]
        return {"mensaje": MSG_CREADO, "tono": "success", "periodo_id": pid, "periodo_cambiado": True,
                "pasos": list(t.steps), "escrituras": len(t.writes),
                "fases_opcionales_omitidas": [x[0] for x in t.optional_skipped]}

    # ------------------------------------------------------------------ E4-11 Revertir ultimo cierre
    def _bloqueos_reversion(self, conn: Connection, nuevo_id: int, anterior_id: int) -> list[dict]:
        """D-E4-05: todo dato del periodo nuevo que la reversion certificada NO borra, y toda referencia (FK) a las filas
        que si borra (designaciones / movimientos del nuevo y movimientos de cierre del anterior)."""
        bloqueos = [c for c in inventario.conteos_periodo(conn, nuevo_id,
                                                           excluir=("designaciones", "estado_consulta_designacion"))
                    if c["filas"]]
        bloqueos += [r for r in inventario.referencias(conn, "designaciones",
                                                       "SELECT id FROM designaciones WHERE periodo_id = %s", [nuevo_id])
                     if r["filas"]]
        bloqueos += [r for r in inventario.referencias(
            conn, "movimientos", "SELECT id FROM movimientos WHERE periodo_id = %s OR (periodo_id = %s AND "
                                 "tipo_movimiento = 'Finalización automática por cierre de período')",
            [nuevo_id, anterior_id]) if r["filas"]]
        return bloqueos

    def _diagnostico(self, ns: dict, conn: Connection, scope=None) -> dict:
        unit = entorno.B12C.TransactionUnit(lambda: entorno.RawTx(conn))
        with unit:
            diag = ns["diagnosticar_reversion_ultimo_cierre"]()
        if diag.get("ok") and scope is not None:
            # Hardening NEXT: ``get_periodo_anterior_cronologico`` certificado filtra con WHERE (a) OR (b) y el
            # inyector B12B agrega el ambito sin parentesis: puede devolver un periodo de OTRO departamento.  La
            # reversion solo procede si el anterior es del departamento de la sesion.
            repo = PeriodosRepository(conn, scope.institution_id, scope.department_id)
            propios = repo.list()
            nuevo = diag["periodo_nuevo"]
            if int(diag["periodo_anterior"]["id"]) not in {int(p["id"]) for p in propios}:
                previos = [p for p in propios if (int(p["anio"]), int(p["semestre"]))
                           < (int(nuevo["anio"]), int(nuevo["semestre"]))]
                diag = {"ok": False, "mensaje": MSG_ANTERIOR_AJENO if previos else MSG_SIN_ANTERIOR,
                        "periodo_nuevo": nuevo, "periodo_anterior": None}
        out = {"ok": bool(diag.get("ok")), "mensaje": diag.get("mensaje"),
               "periodo_nuevo": _period(diag.get("periodo_nuevo")),
               "periodo_anterior": _period(diag.get("periodo_anterior"))}
        for k in ("designaciones_nuevo", "movimientos_nuevo", "renovaciones_nuevo", "cierres_anterior",
                  "finalizadas_anterior", "activas_anterior"):
            out[k] = int(diag.get(k, 0) or 0)
        out["bloqueos"] = []
        if out["ok"]:
            out["bloqueos"] = self._bloqueos_reversion(conn, int(out["periodo_nuevo"]["id"]),
                                                       int(out["periodo_anterior"]["id"]))
        out["puede_revertir"] = out["ok"] and not out["bloqueos"]
        if out["ok"] and out["bloqueos"]:
            out["mensaje_bloqueo"] = MSG_REVERTIR_DEPENDENCIAS.format(
                nombre=out["periodo_nuevo"]["nombre"], lista=", ".join(f"{b['etiqueta']}: {b['filas']}"
                                                                        for b in out["bloqueos"]))
        out["huella"] = _huella({k: v for k, v in out.items() if k != "huella"})
        return out

    def revertir_diagnostico(self, record: SessionRecord) -> dict:
        scope = self.periodos.scope(record)
        base = {"info": INFO_REVERTIR, "es_superadmin": self._es_superadmin(record)}
        if not base["es_superadmin"]:
            return {**base, "mensaje_permiso": MSG_SOLO_SUPERADMIN_REVERTIR}
        ns = self._ns(record, scope)
        return {**base, **self._leer(lambda conn: self._diagnostico(ns, conn, scope))}

    def revertir(self, record: SessionRecord, data: dict) -> dict:
        scope = self.periodos.scope(record)
        data = data if isinstance(data, dict) else {}
        if not self._es_superadmin(record):
            raise PeriodosError(403, "SOLO_SUPERADMIN", MSG_SOLO_SUPERADMIN_REVERTIR, "PermissionError")
        if not all(data.get(k) is True for k in ("confirmar_1", "confirmar_2", "confirmar_3")):
            raise PeriodosError(422, "CONFIRMATION_REQUIRED", MSG_REVERTIR_CONFIRMAR)
        observaciones = data.get("observaciones", "")
        if not isinstance(observaciones, str):
            raise PeriodosError(422, "INVALID", MSG_VALOR_INVALIDO)
        op = self._op(record, "revertir_ultimo_cierre_periodo", ACTION_WRITE)
        ns = self._ns(record, scope)

        def body(conn: Connection):
            self._lock(conn, scope)
            diag = self._diagnostico(ns, conn, scope)
            if diag["huella"] != data.get("huella"):
                raise PeriodosError(409, "STALE", f"{MSG_STALE} [B12I: diagnosticar_reversion_ultimo_cierre]",
                                    "StaleDecisionError")
            if not diag["ok"]:
                raise PeriodosError(409, "NO_REVERSIBLE", diag["mensaje"])
            if diag["bloqueos"]:
                raise PeriodosError(409, "DEPENDENCIAS", diag["mensaje_bloqueo"], "ReversionBloqueada")
            unit = entorno.B12C.TransactionUnit(lambda: entorno.RawTx(conn))
            with unit:
                unit.step("revertir")
                res = ns["revertir_ultimo_cierre_periodo"](observaciones=observaciones)
                unit.trace.lock_statement = 0  # el lock de la operacion se tomo antes, en esta misma transaccion
                unit.commit()
            return res, len(unit.trace.writes), {}

        res = self._ejecutar(op, PREFIX_REVERTIR, body)
        return {"mensaje": f"Cierre revertido. Período eliminado: {res['periodo_eliminado']}. Período reabierto: "
                           f"{res['periodo_reabierto']}. Designaciones reactivadas: {res['designaciones_reactivadas']}.",
                "tono": "success", "periodo_cambiado": True, "resultado": res}

    # ------------------------------------------------------------------ E4-12 Eliminar periodo (solo vacio)
    def _inventario(self, conn: Connection, scope, periodo_id: int) -> dict:
        repo = PeriodosRepository(conn, scope.institution_id, scope.department_id)
        periodo = repo.by_id(periodo_id)
        if periodo is None:
            raise PeriodosError(404, "NOT_FOUND", MSG_PERIODO_NO_ENCONTRADO)
        conteos = inventario.conteos_periodo(conn, periodo_id)
        movs = inventario.movimientos_periodo(conn, periodo_id)
        apertura = inventario.apertura_automatica(periodo, movs)
        cierres = inventario.cierres_generados_por(conn, scope.institution_id, scope.department_id, periodo["nombre"])
        bloqueos = [c for c in conteos if c["filas"]]
        if movs and apertura is None:
            bloqueos.append({"tabla": "movimientos", "filas": len(movs),
                             "etiqueta": "Movimientos (además de la apertura automática, o apertura no identificable)"})
        if cierres:
            bloqueos.append({"tabla": "movimientos", "filas": cierres,
                             "etiqueta": "Finalizaciones automáticas del período anterior generadas al crear este período"})
        restantes = [p for p in repo.list() if int(p["id"]) != periodo_id]
        proximo = restantes[0] if restantes else None
        out = {"periodo": _period(periodo), "conteos": conteos, "movimientos": len(movs),
               "apertura_automatica": None if apertura is None else int(apertura["id"]), "bloqueos": bloqueos,
               "vacio": not bloqueos, "proximo_activo": _period(proximo) if periodo["estado"] == "Abierto" else None,
               "texto_confirmacion": f"ELIMINAR {periodo['nombre']}"}
        out["mensaje"] = None if out["vacio"] else MSG_CON_DATOS
        out["huella"] = _huella({k: v for k, v in out.items() if k != "huella"})
        return out

    @staticmethod
    def _periodo_id(value: Any) -> int:
        pid = core.to_int_or_none(value)
        if pid is None or isinstance(value, bool):
            raise PeriodosError(422, "INVALID_PERIOD", MSG_PERIODO_INVALIDO)
        return pid

    def eliminar_diagnostico(self, record: SessionRecord, data: dict) -> dict:
        scope = self.periodos.scope(record)
        base = {"info": INFO_ELIMINAR, "es_superadmin": self._es_superadmin(record)}
        if not base["es_superadmin"]:
            return {**base, "mensaje_permiso": MSG_SOLO_SUPERADMIN_ELIMINAR}
        data = data if isinstance(data, dict) else {}
        if data.get("periodo_id") is None:
            return base
        pid = self._periodo_id(data.get("periodo_id"))
        return {**base, **self._leer(lambda conn: self._inventario(conn, scope, pid))}

    def eliminar(self, record: SessionRecord, data: dict) -> dict:
        scope = self.periodos.scope(record)
        data = data if isinstance(data, dict) else {}
        if not self._es_superadmin(record):
            raise PeriodosError(403, "SOLO_SUPERADMIN", MSG_SOLO_SUPERADMIN_ELIMINAR, "PermissionError")
        pid = self._periodo_id(data.get("periodo_id"))
        observaciones = data.get("observaciones", "")
        if not isinstance(observaciones, str) or not isinstance(data.get("texto_confirmacion", ""), str):
            raise PeriodosError(422, "INVALID", MSG_VALOR_INVALIDO)
        if data.get("confirmar") is not True:
            raise PeriodosError(422, "CONFIRMATION_REQUIRED", MSG_ELIMINAR_CONFIRMAR)
        op = self._op(record, "eliminar_periodo", ACTION_DELETE, "periodo_id", pid)
        ns = self._ns(record, scope)

        def body(conn: Connection):
            self._lock(conn, scope)
            inv = self._inventario(conn, scope, pid)
            esperado = inv["texto_confirmacion"]
            if str(data.get("texto_confirmacion") or "").strip() != esperado:
                raise PeriodosError(422, "CONFIRMATION_TEXT", MSG_ELIMINAR_TEXTO.format(esperado=esperado))
            if inv["huella"] != data.get("huella"):
                raise PeriodosError(409, "STALE", f"{MSG_STALE} [B12I: inventario del período]", "StaleDecisionError")
            if not inv["vacio"]:
                raise PeriodosError(409, "CON_DATOS", MSG_CON_DATOS, "PeriodoConDatos")
            repo = PeriodosRepository(conn, scope.institution_id, scope.department_id)
            periodo = inv["periodo"]
            if inv["apertura_automatica"] is not None and repo.delete_movement(inv["apertura_automatica"], pid) != 1:
                raise PeriodosError(409, "STALE", f"{MSG_STALE} [B12I: apertura automática]", "StaleDecisionError")
            if repo.delete_period(pid) != 1:
                raise PeriodosError(409, "STALE", f"{MSG_STALE} [B12I: período]", "StaleDecisionError")
            actual = repo.last_period()
            detalle = (f"Se eliminó el período vacío {periodo['nombre']} ({periodo['fecha_inicio']} al "
                       f"{periodo['fecha_fin']}). Movimientos automáticos de apertura eliminados: {inv['movimientos']}.")
            if periodo["estado"] == "Abierto" and actual is not None:
                repo.close_all_open()
                repo.open_one(int(actual["id"]))
                detalle += f" Luego se abrió automáticamente el período {actual['nombre']}."
            unit = entorno.B12C.TransactionUnit(lambda: entorno.RawTx(conn))
            with unit:  # registrar_movimiento certificado (l. 4424), mismo texto que eliminar_periodo (l. 11558)
                ns["registrar_movimiento"]("Eliminación de período vacío", "", "", detalle, observaciones,
                                           int(actual["id"]) if actual is not None else None)
                unit.trace.lock_statement = 0
                unit.commit()
            res = {"periodo_eliminado": periodo, "periodo_activo": _period(actual) if periodo["estado"] == "Abierto"
                   else None, "apertura_eliminada": inv["apertura_automatica"] is not None}
            return res, repo.mutating_statements + len(unit.trace.writes), {}

        res = self._ejecutar(op, PREFIX_ELIMINAR, body)
        p, activo = res["periodo_eliminado"], res["periodo_activo"]
        mensaje = f"Período {p['nombre']} eliminado correctamente."
        if activo is not None:
            mensaje += f" Quedó activo: {activo['nombre']} ({activo['fecha_inicio']} al {activo['fecha_fin']})."
        elif p["estado"] == "Abierto":
            mensaje += " No quedan períodos disponibles para abrir."
        return {"mensaje": mensaje, "tono": "success", "periodo_cambiado": True, "resultado": res}

    # ------------------------------------------------------------------ E4-12 / P-12b Reparar finalizaciones automaticas
    def _reparacion(self, ns: dict, conn: Connection, scope) -> dict:
        """Diagnostico P-12b sobre el periodo abierto del ambito: deteccion certificada
        (``_finalizaciones_automaticas_reactivables``) + preflight NEXT estricto.  Solo lectura."""
        repo = PeriodosRepository(conn, scope.institution_id, scope.department_id)
        abierto = repo.open_period()
        out: dict = {"periodo": _period(abierto), "visible": False, "movimientos_cierre": 0,
                     "designaciones_reactivables": 0, "bloqueos": [], "puede_reparar": False}
        if abierto is not None:
            pid, nombre = int(abierto["id"]), abierto["nombre"]
            movs = inventario.cierres_del_periodo(conn, pid)
            out["visible"] = bool(movs)
        if out["visible"]:
            finalizadas = inventario.finalizadas_del_periodo(conn, scope.institution_id, scope.department_id, pid)
            bloqueos, ids_designaciones = inventario.reparacion_cierres(
                scope.institution_id, scope.department_id, abierto, repo.last_period(),
                {p["nombre"] for p in repo.list()}, movs, finalizadas, ns["_texto_designacion_para_match"])
            ids_movimientos = {int(m["id"]) for m in movs}
            unit = entorno.B12C.TransactionUnit(lambda: entorno.RawTx(conn))
            with unit:
                cert = ns["_finalizaciones_automaticas_reactivables"](pid, None)
            if not bloqueos and (set(cert["ids_reactivar"]) != ids_designaciones
                                 or set(cert["movimientos_ids"]) != ids_movimientos):
                bloqueos.append({"tabla": "movimientos", "filas": len(movs), "etiqueta":
                                 "la detección certificada no coincide con la identificación exacta (caso ambiguo)"})
            bloqueos += [r for r in inventario.referencias(conn, "movimientos",
                                                           "SELECT id FROM movimientos WHERE id = ANY(%s)",
                                                           [sorted(ids_movimientos)]) if r["filas"]]
            out.update({"movimientos_cierre": len(ids_movimientos), "designaciones_reactivables": len(ids_designaciones),
                        "ids_designaciones": sorted(ids_designaciones), "ids_movimientos": sorted(ids_movimientos),
                        "bloqueos": bloqueos, "puede_reparar": not bloqueos})
            out["mensaje"] = (AVISO_REPARAR.format(nombre=nombre, designaciones=len(ids_designaciones),
                                                   movimientos=len(ids_movimientos)) if not bloqueos else
                              MSG_REPARAR_BLOQUEADO.format(nombre=nombre, movimientos=len(ids_movimientos),
                                                           lista="; ".join(f"{b['etiqueta']}: {b['filas']}"
                                                                           for b in bloqueos)))
        out["huella"] = _huella({k: v for k, v in out.items() if k != "huella"})
        return out

    def reparar_diagnostico(self, record: SessionRecord) -> dict:
        """Bloque P-12b de la pestaña "🗑️ Eliminar período" (certificado: solo superadmin, solo si hay algo que reparar)."""
        scope = self.periodos.scope(record)
        if not self._es_superadmin(record):
            return {"es_superadmin": False, "visible": False}
        ns = self._ns(record, scope)
        return {"es_superadmin": True, "boton": BOTON_REPARAR, **self._leer(lambda conn: self._reparacion(ns, conn, scope))}

    def reparar(self, record: SessionRecord, data: dict) -> dict:
        scope = self.periodos.scope(record)
        data = data if isinstance(data, dict) else {}
        if not self._es_superadmin(record):
            raise PeriodosError(403, "SOLO_SUPERADMIN", MSG_SOLO_SUPERADMIN_REPARAR, "PermissionError")
        if not isinstance(data.get("huella"), str):
            raise PeriodosError(422, "INVALID", MSG_VALOR_INVALIDO)
        op = self._op(record, "reactivar_finalizaciones_automaticas_periodo", ACTION_WRITE)
        ns = self._ns(record, scope)

        def body(conn: Connection):
            self._lock(conn, scope)
            diag = self._reparacion(ns, conn, scope)
            if diag["huella"] != data.get("huella"):
                raise PeriodosError(409, "STALE", f"{MSG_STALE} [B12I: finalizaciones automáticas]",
                                    "StaleDecisionError")
            if not diag["visible"]:
                raise PeriodosError(409, "NADA", MSG_NADA_REPARAR)
            if diag["bloqueos"]:
                raise PeriodosError(409, "NO_REPARABLE", diag["mensaje"], "ReparacionBloqueada")
            pid = int(diag["periodo"]["id"])
            unit = entorno.B12C.TransactionUnit(lambda: entorno.RawTx(conn))
            with unit:
                unit.step("reparar")
                res = ns["reactivar_finalizaciones_automaticas_periodo"](pid)
                unit.trace.lock_statement = 0  # el lock de la operacion se tomo antes, en esta misma transaccion
                unit.commit()
            # verificacion posterior en la misma transaccion: exactamente lo diagnosticado, nada mas
            activas = conn.execute("SELECT count(*) FROM designaciones WHERE id = ANY(%s) AND estado = 'Activa'",
                                   [diag["ids_designaciones"]]).fetchone()[0]
            if (res.get("designaciones_reactivadas") != diag["designaciones_reactivables"]
                    or res.get("movimientos_cierre_eliminados") != diag["movimientos_cierre"]
                    or activas != diag["designaciones_reactivables"] or inventario.cierres_del_periodo(conn, pid)):
                raise PeriodosError(409, "STALE", f"{MSG_STALE} [B12I: finalizaciones automáticas]",
                                    "StaleDecisionError")
            return res, len(unit.trace.writes), {}

        res = self._ejecutar(op, PREFIX_REPARAR, body)
        return {"mensaje": MSG_REPARADO.format(designaciones=res.get("designaciones_reactivadas", 0),
                                               movimientos=res.get("movimientos_cierre_eliminados", 0)),
                "tono": "success", "periodo_cambiado": False, "resultado": res}


__all__ = ["CicloPeriodosService"]
