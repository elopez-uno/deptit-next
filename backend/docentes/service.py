"""Reglas de negocio de Docentes (B13-FIX02) sobre la sesion y el contexto de ``auth``.

Alcance (decision humana, docs/docentes_analysis.md §10): base maestra (listado, busqueda, detalle), alta de docente
propio, edicion v168 (identidad institucional, cambio de CUIL con migracion de referencias, baja/reactivacion por
estado), eliminacion fisica simple e integral, alta de prestado, finalizar prestamo, reparar CUIL huerfano y carga
rapida simple.  Las acciones que crean designaciones (E4-08) las coordina ``integraciones/registro_designacion.py``
con los contratos ``cuil_existente`` / ``guardar_propio_desde_existente`` de este servicio y el alta de Designaciones;
la carga rapida integral (E4-09), ``integraciones/carga_integral.py`` con ``alta_desde_carga_integral`` /
``actualizar_desde_carga_integral``; las pestañas Plantel, Equipos y Resumen, la composicion de Etapa 4.

Cada writer certificado que la UI invoca es una operacion propia (B12H: ``correlation_id`` por writer):
1. comprobaciones de la UI (campos, confirmaciones, rama de la pantalla) sobre lecturas frescas: sin evento;
2. B10 del writer (``docentes.write`` / ``docentes.delete`` / ``movimientos.write``): DENIED;
3. B12I capa U: la fila que el usuario vio (``huella``) se relee fresca; si cambio -> FAILED ``StaleDecisionError``;
4. cuerpo en una transaccion -> SUCCESS ``commit_seq`` 1 en esa transaccion; sin cambios -> SUCCESS POST_OPERATION;
   error -> ROLLBACK + FAILED.  Como en el certificado, el docente y su movimiento son COMMITs distintos: si el
   movimiento falla, el docente ya quedo confirmado.
El ambito (institucion/departamento) sale SIEMPRE de la sesion revalidada; ningun id de tenant llega del cliente.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable, Optional

from psycopg import Connection

import audit
from auth import policy
from auth.service import AuthService, SessionRecord
from periodos.service import MSG_AUDIT_POST, MSG_DB_READ, MSG_DB_TRANSACTION, MSG_INSTITUTIONAL, MSG_STALE
from periodos.service import denial_message, scope_message

from . import carga, identidad, rules
from .repository import DocentesRepository

log = logging.getLogger("deptit_next.docentes")

ACTION_READ = policy.Action("docentes", policy.OP_READ, policy.SCOPE_DEPARTMENT)
ACTION_WRITE = policy.Action("docentes", policy.OP_WRITE, policy.SCOPE_DEPARTMENT)
ACTION_DELETE = policy.Action("docentes", policy.OP_DELETE, policy.SCOPE_DEPARTMENT)
ACTION_MOVEMENT = policy.Action("movimientos", policy.OP_WRITE, policy.SCOPE_DEPARTMENT)


@dataclass(frozen=True)
class WriterSpec:
    """Writer del registro B10 (legacy_write_actions.py) y su etiqueta B12H (audit_actor.py)."""
    name: str
    action: policy.Action
    entity_type: str
    entity_param: Optional[str]


W_GUARDAR = WriterSpec("guardar_docente", ACTION_WRITE, "docente", "cuil")
W_ACTUALIZAR = WriterSpec("actualizar_docente", ACTION_WRITE, "docente", "cuil")
W_ELIMINAR = WriterSpec("eliminar_docente", ACTION_DELETE, "docente", "cuil")
W_PRESTAMO = WriterSpec("registrar_prestamo_docente_v174", ACTION_WRITE, "prestamo_docente", "cuil")
W_FIN_PRESTAMO = WriterSpec("finalizar_prestamo_docente_v174", ACTION_WRITE, "prestamo_docente", "cuil")
W_MIGRAR = WriterSpec("migrar_referencias_cuil_v168", ACTION_WRITE, "docente", None)
W_MOVIMIENTO = WriterSpec("registrar_movimiento", ACTION_MOVEMENT, "movimiento", "cuil")

# --- textos certificados (entry l. 59801-61761 y funciones citadas en docs/docentes_analysis.md) --------------
MSG_ALTA_REQUERIDOS = "Completá al menos Apellido/s, Nombre/s y CUIL."
MSG_ALTA_OK = "Docente registrado correctamente."
PREFIX_ALTA = "No se pudo registrar el docente: "
MSG_EDIT_OK = "Docente actualizado correctamente."
MSG_ELIMINAR_CONFIRMAR = "Primero confirmá la eliminación."
MSG_CUIL_SELECCION_INVALIDO = "El CUIL seleccionado no es válido."
MSG_ELIMINAR_NO_LOCAL = "No se encontró el registro local del docente en el departamento actual."
MSG_SIN_PERIODO_PRESTAMO = "No hay período abierto para registrar el préstamo."
MSG_PROPIO_LOCAL = "Este CUIL ya está registrado como docente propio en el departamento actual."
MSG_YA_PROPIO = "El docente ya existe como propio en el departamento actual."
MSG_FIN_CONFIRMAR = "Confirmá la finalización del préstamo."
MSG_FIN_OK = "Préstamo finalizado. El docente ya no integra el plantel operativo del período abierto."
MSG_FIN_SIN_CAMBIO = "El préstamo ya estaba finalizado o no estaba activo."
MSG_REPARAR_CONFIRMAR = "Confirmá primero que el CUIL huérfano pertenece a esta misma persona."
PREFIX_REPARAR = "No se pudo reparar el CUIL anterior: "
MSG_CARGA_DUPLICADOS = "No se cargó nada. Hay duplicados: marcá la confirmación si realmente querés avanzar."
MSG_CARGA_SIN_FILAS = "No pude detectar filas válidas. Revisá que la tabla tenga CUIL y datos de docente."
MSG_OTRO_DEPTO = ("El CUIL ya pertenece a un docente registrado en otro departamento. "
                  "Seleccioná cómo debe incorporarse al departamento actual.")
# Decision humana (§10): con un periodo historico abierto la base maestra no inventa la etiqueta v182/v183.  Desde E4-02
# el puerto ``plantel_cuiles`` (capa de composicion) entrega el plantel historico; sin puerto se conserva este texto.
MSG_HISTORICO_NO_DISPONIBLE = "No disponible: requiere el plantel histórico (pendiente de Designaciones)"
# get_docentes v183 (entry l. 40115-40130): etiqueta con un periodo historico abierto (pisa la v182).
ESTADO_HISTORICO_VIGENTE = "Vigente al cierre del período en contexto"
ESTADO_HISTORICO_FUERA = "Fuera de la dotación al cierre del período en contexto"
# Textos propios de la API (no existen en Streamlit: alli la seleccion siempre sale de la tabla en pantalla).
MSG_DOCENTE_NO_ENCONTRADO = "No se encontró el docente seleccionado. Actualizá la pantalla."
MSG_ORIGEN_NO_ENCONTRADO = "El docente elegido ya no figura entre los docentes activos de otros departamentos."
MSG_VALOR_INVALIDO = "Uno de los valores enviados no es válido para este formulario."

MOV_ALTA = "Alta de docente"
MOV_BAJA = "Baja de docente"
MOV_EDICION = "Edición de docente"
MOV_ALTA_PRESTADO = "Alta de docente prestado"
MOV_FIN_PRESTAMO = "Finalización de préstamo docente"
MOV_ACTUALIZACION = "Actualización de docente existente"

ROW_FIELDS = ("cuil", "legajo", "apellido", "nombres", "nombre_completo", "titulo", "titulo_posgrado",
              "antiguedad_anios", "nivel_posgrado_salarial", "email", "telefono", "ref_legajo_fisico",
              "tipo_docente", "observaciones", "estado", "fecha_alta", "fecha_finalizacion", "estado_periodo_abierto")


class DocentesError(Exception):
    """Error controlado para la UI.  ``error_class`` = clase de la excepcion certificada equivalente (B12H)."""

    def __init__(self, status: int, code: str, message: str, error_class: str = "ValueError"):
        super().__init__(message)
        self.status, self.code, self.message, self.error_class = status, code, message, error_class


class _Info(Exception):
    """Resultado sin cambios que la UI certificada muestra como ``st.info`` (no es error)."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


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
    return {k: row.get(k) for k in ("id", "nombre", "anio", "semestre", "fecha_inicio", "fecha_fin", "estado")}


def _jsonable(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _clean_rows(rows: list[dict]) -> list[dict]:
    return [{k: _jsonable(v) for k, v in r.items()} for r in rows]


def _huella(row: dict, open_period: Optional[dict]) -> str:
    payload = {k: _jsonable(row.get(k)) for k in ROW_FIELDS}
    payload["_periodo_abierto"] = None if open_period is None else int(open_period["id"])
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _text(value: Any) -> str:
    """Valor de un ``st.text_input``/``st.text_area``: texto tal cual (sin ``strip``)."""
    return "" if value is None else str(value)


def _cuil_key_v204(valor: Any) -> str:
    return re.sub(r"\D", "", str(valor or "")).strip()


class DocentesService:
    def __init__(self, pool, auth: AuthService, audit_store: audit.AuditStore, *,
                 today: Callable[[], date] = date.today, now: Callable[[], datetime] = datetime.now,
                 transaction: Optional[Callable[[], AbstractContextManager[Connection]]] = None,
                 plantel_cuiles: Optional[Callable[[Connection, int, int, int], list]] = None):
        self.auth = auth
        self.audit_store = audit_store
        self.today = today
        self.now = now
        # Puerto E4-02 (D-E4-01): CUIL del plantel ``get_plantel_periodo`` (Comisiones) leidos en la MISMA conexion;
        # lo conecta ``main.py`` desde la capa de composicion (Docentes no importa Comisiones).
        self._plantel_cuiles = plantel_cuiles
        # Unidad de trabajo = un COMMIT certificado (conexion del pool: confirma al salir sin error).
        self._transaction = transaction or (lambda: pool.connection(timeout=5))

    # ------------------------------------------------------------------ contexto (B12B) y modulo visible
    def scope(self, record: SessionRecord) -> Scope:
        self.auth.apply_default_context(record)
        user, session_scope = record.user, record.scope
        effective = policy.normalize_role(user.get("rol"))
        visible = policy.visible_modules(effective, session_scope.get(policy.DEPARTMENT_SCOPE_KEY))
        resolution = self.auth.resolve_scope(record)
        if resolution.reason is not None:
            raise DocentesError(409, "SCOPE_NOT_VERIFIED", scope_message(resolution))
        if not any(m[0] == "docentes" for m in visible) or resolution.department is None:
            raise DocentesError(409, "SCOPE_INSTITUTIONAL", MSG_INSTITUTIONAL)
        return Scope(int(resolution.institution["id"]), int(resolution.department["id"]),
                     resolution.institution, resolution.department)

    def _require_read(self, record: SessionRecord) -> policy.ActorContext:
        actor = policy.actor_from_session(record.user, record.scope)
        decision = policy.decide(actor, ACTION_READ)
        if not decision.allowed:
            raise DocentesError(403, "DENIED", denial_message(decision, ACTION_READ))
        return actor

    def _read(self, scope: Scope, fn: Callable[[DocentesRepository], Any]) -> Any:
        try:
            with self._transaction() as conn:
                conn.execute("SET TRANSACTION READ ONLY")
                return fn(DocentesRepository(conn, scope.institution_id, scope.department_id))
        except DocentesError:
            raise
        except Exception as exc:
            log.error("docentes: lectura fallida: %s", type(exc).__name__)
            raise DocentesError(503, "DB_READ", MSG_DB_READ) from None

    # ------------------------------------------------------------------ base maestra (get_docentes v204 + v182/v183)
    def _base_maestra(self, repo: DocentesRepository) -> dict:
        open_period, last_period = repo.open_period(), repo.last_period()
        periodo_actual_id = None
        if last_period and last_period.get("id") is not None:
            periodo_actual_id = int(last_period["id"])
        rows = repo.docentes()
        des = repo.designaciones_trayectoria() if rows else []
        prest = repo.prestamos_estado(periodo_actual_id) if rows and periodo_actual_id is not None else []

        hoy = self.today()
        activos_actuales: set[str] = set()
        if periodo_actual_id is not None:
            for d in des:
                if d.get("periodo_id") is not None and int(d["periodo_id"]) == periodo_actual_id \
                        and str(d.get("estado") or "Activa").strip().casefold() == "activa":
                    k = _cuil_key_v204(d.get("cuil"))
                    if k:
                        activos_actuales.add(k)
        for p in prest:
            if str(p.get("estado") or "Activo").strip().casefold() == "activo":
                k = _cuil_key_v204(p.get("cuil"))
                if k:
                    activos_actuales.add(k)

        fechas_alta: dict[str, date] = {}
        fechas_fin: dict[str, date] = {}
        con_designacion: set[str] = set()
        for d in des:
            k = _cuil_key_v204(d.get("cuil"))
            if not k:
                continue
            con_designacion.add(k)
            desde = rules.safe_date(d.get("fecha_desde"), None)
            if desde is not None and (fechas_alta.get(k) is None or desde < fechas_alta[k]):
                fechas_alta[k] = desde
            fin = rules.safe_date(d.get("fecha_finalizacion_efectiva"), None)
            if fin is None:
                fin = rules.safe_date(d.get("fecha_hasta"), None)
            if fin is not None and fin <= hoy and (fechas_fin.get(k) is None or fin > fechas_fin[k]):
                fechas_fin[k] = fin

        # v182/v183: periodo abierto historico (no es el ultimo cronologico) -> etiqueta segun el plantel al cierre.
        historico = bool(open_period and last_period and int(open_period["id"]) != int(last_period["id"]))
        claves_plantel: Optional[set[str]] = None
        if historico and rows and self._plantel_cuiles is not None:
            claves_plantel = {x for x in (rules.clave_cuil(c) for c in
                                          self._plantel_cuiles(repo._conn, repo.inst, repo.dep, int(open_period["id"])))
                              if x}
        out = []
        for r in rows:
            k = _cuil_key_v204(r.get("cuil"))
            activo = bool(k and k in activos_actuales)
            alta = fechas_alta.get(k)
            fin = None if activo else fechas_fin.get(k)
            if historico and claves_plantel is not None:
                estado_op = (ESTADO_HISTORICO_VIGENTE if rules.clave_cuil(r.get("cuil")) in claves_plantel
                             else ESTADO_HISTORICO_FUERA)
            elif historico:
                estado_op = MSG_HISTORICO_NO_DISPONIBLE
            elif activo:
                estado_op = "Activo en período actual"
            elif periodo_actual_id is None:
                estado_op = "Sin período actual"
            elif k in con_designacion:
                estado_op = "Finalizado / sin designación activa"
            else:
                estado_op = "Sin designación registrada"
            row = dict(r)
            row["fecha_alta"] = alta.isoformat() if alta is not None else ""
            row["fecha_finalizacion"] = fin.isoformat() if fin is not None else ""
            row["estado_periodo_abierto"] = estado_op
            row = {f: _jsonable(row.get(f)) for f in ROW_FIELDS}
            row["huella"] = _huella(row, open_period)
            out.append(row)
        return {"docentes": out, "abierto": open_period, "actual": last_period, "historico": historico}

    @staticmethod
    def _row(base: dict, cuil: Any) -> Optional[dict]:
        cuil = "" if cuil is None else str(cuil)
        return next((r for r in base["docentes"] if str(r.get("cuil")) == cuil), None)

    def overview(self, record: SessionRecord) -> dict:
        scope = self.scope(record)
        actor = self._require_read(record)
        base = self._read(scope, self._base_maestra)
        return {
            "contexto": {"institucion": _named(scope.institution), "departamento": _named(scope.department)},
            "abierto": _period(base["abierto"]),
            "actual": _period(base["actual"]),
            "historico": base["historico"],
            "docentes": base["docentes"],
            "catalogos": {"estados": rules.ESTADOS_DOCENTE, "estados_baja": rules.ESTADOS_BAJA_DOCENTE,
                          "tipos": rules.TIPOS_DOCENTE, "niveles_posgrado": rules.NIVELES_POSGRADO_SALARIAL,
                          "antiguedad_min": rules.ANTIGUEDAD_MIN, "antiguedad_max": rules.ANTIGUEDAD_MAX},
            "permisos": {
                "puede_escribir": policy.decide(actor, ACTION_WRITE).allowed,
                "puede_borrar": policy.decide(actor, ACTION_DELETE).allowed,
                "es_superadmin": policy.normalize_role(record.user.get("rol")) == policy.ROLE_SUPERADMIN,
            },
        }

    # ------------------------------------------------------------------ ficha: referencias, prestamo, huerfanos
    @staticmethod
    def _referencias(repo: DocentesRepository, cuil: Any) -> dict:
        """``_diagnosticar_referencias_docente_conn`` (solo el departamento operativo)."""
        clave = rules.clave_cuil(cuil)
        vacio = {"designaciones": [], "comisiones": [], "investigacion": [], "extension": [],
                 "actividades_especiales": [], "total": 0}
        if not clave:
            return vacio
        ref = repo.referencias(clave)
        periodos = {int(p["id"]): p.get("nombre") for p in repo.periodos_nombres()}

        def periodo(pid):
            return periodos.get(int(pid)) if pid is not None else None

        designaciones = [{"id": d["id"], "periodo": periodo(d["periodo_id"]), "periodo_id": d["periodo_id"],
                          "cargo": d["cargo"], "dedicacion": d["dedicacion"], "horas": d["horas"],
                          "tipo_designacion": d["tipo_designacion"], "ad_honorem": d["ad_honorem"],
                          "fecha_desde": d["fecha_desde"], "fecha_hasta": d["fecha_hasta"], "estado": d["estado"]}
                         for d in ref["designaciones"]]
        comisiones = ref["comisiones"]
        if comisiones:
            info = {int(c["id"]): c for c in repo.comisiones_info()}
            if info:
                out = []
                for a in comisiones:
                    co = info.get(int(a["comision_id"])) if a.get("comision_id") is not None else None
                    pid = co.get("periodo_id") if co else None
                    out.append({"id": a["id"], "periodo": periodo(pid), "comision": co.get("nombre_comision") if co
                                else None, "turno": co.get("turno") if co else None,
                                "modalidad": co.get("modalidad") if co else None, "comision_id": a["comision_id"],
                                "cargo_rol": a["cargo_rol"], "horas": a["horas"], "estado": a["estado"],
                                "observaciones": a["observaciones"]})
                comisiones = out
        proyectos = {}
        for key in ("investigacion", "extension"):
            proyectos[key] = [{"id": i["id"], "periodo": periodo(i["periodo_id"]), "periodo_id": i["periodo_id"],
                               "codigo": i["codigo"], "proyecto": i["proyecto"], "rol": i["rol"],
                               "horas": i["horas"], "estado": i["estado"]} for i in ref[key]]
        actividades = ref["actividades_especiales"]
        if actividades:
            titulos = {int(a["id"]): a.get("titulo") for a in repo.actividades_info()}
            actividades = [{"id": a["id"], "periodo": periodo(a["periodo_id"]), "periodo_id": a["periodo_id"],
                            "actividad": titulos.get(int(a["actividad_id"])), "actividad_id": a["actividad_id"],
                            "rol": a["rol"], "estado": a["estado"], "observaciones": a["observaciones"]}
                           for a in actividades]
        result = {"designaciones": designaciones, "comisiones": comisiones,
                  "investigacion": proyectos["investigacion"], "extension": proyectos["extension"],
                  "actividades_especiales": actividades}
        result["total"] = sum(len(v) for v in result.values())
        return result

    @staticmethod
    def _prestamo_activo(repo: DocentesRepository, period_id: int, cuil: Any) -> Optional[dict]:
        clave = rules.clave_cuil(cuil)
        for pr in repo.prestamos_periodo(period_id, solo_activos=True):
            if rules.clave_cuil(pr.get("cuil")) == clave:
                return pr
        return None

    def ficha(self, record: SessionRecord, cuil: Any) -> dict:
        scope = self.scope(record)
        self._require_read(record)

        def read(repo: DocentesRepository) -> dict:
            base = self._base_maestra(repo)
            fila = self._row(base, cuil)
            if fila is None:
                raise DocentesError(404, "NOT_FOUND", MSG_DOCENTE_NO_ENCONTRADO)
            prestamo = None
            abierto = base["abierto"]
            if str(fila.get("tipo_docente") or "Propio").strip() == "Prestado" and abierto:
                pr = self._prestamo_activo(repo, int(abierto["id"]), fila["cuil"])
                if pr is not None:
                    origen = pr.get("departamento_origen") or self._origen_local(repo, fila["cuil"]) or "-"
                    prestamo = {"departamento_origen": origen, "fecha_desde": _jsonable(pr.get("fecha_desde")) or "-"}
                prestamo = {"activo": prestamo}
            refs = self._referencias(repo, fila["cuil"])
            refs = {k: (_clean_rows(v) if isinstance(v, list) else v) for k, v in refs.items()}
            return {"docente": fila, "referencias": refs, "prestamo": prestamo,
                    "huerfanos": identidad.cuiles_huerfanos(repo)}

        return self._read(scope, read)

    @staticmethod
    def _origen_local(repo: DocentesRepository, cuil: Any) -> str:
        """``_origen_prestado_local_v174``: origen leido de la observacion de la ficha local."""
        fila = repo.docente_existe(rules.clave_cuil(cuil)) if str(cuil or "") else None
        if fila is None or str(fila.get("cuil")) != str(cuil):
            return ""
        return rules.departamento_origen_desde_obs_prestado(fila.get("observaciones", ""))

    # ------------------------------------------------------------------ lecturas del alta
    def verificar_cuil(self, record: SessionRecord, cuil: Any) -> dict:
        scope = self.scope(record)
        self._require_read(record)
        cuil_limpio = rules.limpiar_cuil(cuil)

        def read(repo: DocentesRepository) -> dict:
            otros = repo.mismo_cuil_otro_departamento(rules.clave_cuil(cuil_limpio)) if str(cuil_limpio).strip() \
                else []
            local = repo.docente_existe(rules.clave_cuil(cuil_limpio)) if cuil_limpio else None
            local_out = None
            if local is not None:
                local_out = {"cuil": local.get("cuil"), "tipo_docente": local.get("tipo_docente"),
                             "nombre": local.get("nombre") or rules.nombre_completo(local.get("apellido"),
                                                                                    local.get("nombres"))}
            return {"cuil_limpio": cuil_limpio,
                    "otros_departamentos": _clean_rows(otros),
                    "local": local_out}

        return self._read(scope, read)

    def prestables(self, record: SessionRecord) -> dict:
        scope = self.scope(record)
        self._require_read(record)
        rows = self._read(scope, lambda repo: repo.prestables())
        return {"docentes": _clean_rows(rows)}

    def modelo_excel(self, record: SessionRecord) -> bytes:
        self.scope(record)
        self._require_read(record)
        return carga.generar_excel_modelo_carga_rapida_docentes(filas_modelo=1000)

    # ------------------------------------------------------------------ B10 + B12H por writer
    def _authorize(self, record: SessionRecord, spec: WriterSpec, entity_raw: Any = None,
                   prefix: str = "") -> audit.Operation:
        actor = policy.actor_from_session(record.user, record.scope)
        audit_actor = audit.actor_from_record(record.user, record.scope, record.meta)
        op = audit.Operation(spec.name, spec.action, spec.entity_type, audit_actor, spec.entity_param, entity_raw)
        decision = policy.decide(actor, spec.action)
        if not decision.allowed:
            self._separate(op, audit.OUTCOME_DENIED, error_code=decision.code,
                           metadata={"b10_decision": decision.code})
            raise DocentesError(403, "DENIED", prefix + denial_message(decision, spec.action), "PermissionError")
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

    def _writer(self, record: SessionRecord, scope: Scope, spec: WriterSpec, body: Callable[[DocentesRepository], Any],
                *, entity_raw: Any = None, prefix: str = "", stale: Optional[Callable[[], None]] = None) -> Any:
        """Un writer certificado completo: B10 -> B12I (``stale``) -> COMMIT con su SUCCESS, o FAILED."""
        op = self._authorize(record, spec, entity_raw, prefix)
        mutated = False
        try:
            if stale is not None:
                stale()
            with self._transaction() as conn:
                repo = DocentesRepository(conn, scope.institution_id, scope.department_id)
                result = body(repo)
                if repo.mutating_statements:
                    try:
                        audit.insert_on(conn, op.event(audit.OUTCOME_SUCCESS, audit.MODE_IN_TRANSACTION, metadata={
                            "commit_seq": 1, "mutating_statements": repo.mutating_statements,
                            "committing_writer": spec.name}))
                    except Exception as exc:
                        log.error("B12H: el evento SUCCESS de %s no pudo insertarse (%s): ROLLBACK", op.name,
                                  audit.error_code_of(exc))
                        raise DocentesError(503, "AUDIT", f"{audit.MSG_PERSIST} [AUDIT_INSERT_FAILED]",
                                            "AuditPersistenceError:AUDIT_INSERT_FAILED") from None
                    mutated = True
        except DocentesError as exc:
            self._separate(op, audit.OUTCOME_FAILED, error_code=exc.error_class, metadata={"coupled_commits": 0})
            raise DocentesError(exc.status, exc.code, prefix + exc.message, exc.error_class) from None
        except (identidad.IdentidadError, identidad.RemanentesError, rules.PosgradoNivelInvalido) as exc:
            self._separate(op, audit.OUTCOME_FAILED, error_code=audit.error_code_of(exc),
                           metadata={"coupled_commits": 0})
            raise DocentesError(409 if not isinstance(exc, rules.PosgradoNivelInvalido) else 422, "REJECTED",
                                prefix + str(exc), type(exc).__name__) from None
        except Exception as exc:
            log.error("docentes: %s falló: %s", op.name, type(exc).__name__)
            self._separate(op, audit.OUTCOME_FAILED, error_code=audit.error_code_of(exc),
                           metadata={"coupled_commits": 0})
            raise DocentesError(503, "DB_ERROR", prefix + MSG_DB_TRANSACTION) from None
        if not mutated:
            if not self._separate(op, audit.OUTCOME_SUCCESS,
                                  metadata={"coupled_commits": 0, "post_reason": "NO_POOLED_COMMIT"}):
                raise DocentesError(503, "AUDIT", MSG_AUDIT_POST)
        return result

    def _movement(self, record: SessionRecord, scope: Scope, *, tipo: str, cuil: Any, nombre: Any, detalle: str,
                  observaciones: Any = "", period_id: Optional[int] = None, prefix: str = "") -> None:
        """``registrar_movimiento`` como writer de primer nivel (la UI certificada lo llama despues del writer)."""
        cuil_txt, nombre_txt = _text(cuil), _text(nombre)
        self._writer(record, scope, W_MOVIMIENTO, lambda repo: repo.insert_movement(
            period_id=period_id, fecha=str(self.today()), tipo=tipo, cuil=cuil_txt, nombre=nombre_txt,
            detalle=detalle, observaciones=_text(observaciones), horas_variacion=0), entity_raw=cuil_txt,
            prefix=prefix)

    def _stale_check(self, scope: Scope, cuil: Any, huella: Any) -> Callable[[], None]:
        """B12I capa U: relee fresca la fila que el usuario vio; si no coincide, no se escribe nada."""
        def check() -> None:
            try:
                base = self._read(scope, self._base_maestra)
            except DocentesError:
                raise DocentesError(503, "FRESH_READ", MSG_DB_READ, "FreshReadError") from None
            fila = self._row(base, cuil)
            if fila is None or not isinstance(huella, str) or fila["huella"] != huella:
                raise DocentesError(409, "STALE", f"{MSG_STALE} [B12I: get_docentes]", "StaleDecisionError")
        return check

    # ------------------------------------------------------------------ cuerpos de writers certificados
    def _guardar_body(self, values: dict) -> Callable[[DocentesRepository], int]:
        """``guardar_docente`` (entry l. 8073): INSERT con el ambito de la sesion."""
        def body(repo: DocentesRepository) -> int:
            return repo.insert_docente(values)
        return body

    def _docente_values(self, cuil, apellido, nombres, legajo, titulo, titulo_posgrado, email, telefono, ref_legajo,
                        estado, tipo_docente="Propio", fecha_alta=None, observaciones="", antiguedad_anios=None,
                        nivel_posgrado_salarial="") -> dict:
        return {"cuil": cuil, "nombre": rules.nombre_completo(apellido, nombres), "apellido": apellido,
                "nombres": nombres, "legajo": legajo, "titulo": titulo, "titulo_posgrado": titulo_posgrado,
                "antiguedad_anios": antiguedad_anios, "nivel_posgrado_salarial": nivel_posgrado_salarial,
                "email": email, "telefono": telefono, "ref_legajo_fisico": ref_legajo, "estado": estado,
                "tipo_docente": tipo_docente,
                "fecha_alta": str(fecha_alta) if fecha_alta else str(self.today()), "observaciones": observaciones}

    def _prestamo_body(self, cuil: str, period_id: int, origen: str, obs: str, fecha_desde: Any):
        """``registrar_prestamo_docente_v174``: activa el prestamo solo para el periodo indicado."""
        def body(repo: DocentesRepository) -> dict:
            if not cuil or period_id is None:
                raise DocentesError(422, "INVALID", "Falta CUIL o período para registrar el préstamo.")
            if self._prestamo_activo(repo, period_id, cuil) is not None:
                return {"cambio": False, "estado": "ya_activo"}
            repo.upsert_prestamo(period_id=period_id, cuil=cuil, origen=origen, fecha_desde=str(fecha_desde),
                                 observaciones=obs, fecha_registro=self.now().isoformat(timespec="seconds"))
            return {"cambio": True, "estado": "activo"}
        return body

    # ------------------------------------------------------------------ Alta de docente propio nuevo
    @staticmethod
    def _antiguedad(value: Any) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int):
            raise DocentesError(422, "INVALID", MSG_VALOR_INVALIDO)
        if not rules.ANTIGUEDAD_MIN <= value <= rules.ANTIGUEDAD_MAX:
            raise DocentesError(422, "INVALID", MSG_VALOR_INVALIDO)
        return value

    @staticmethod
    def _fecha(value: Any) -> date:
        try:
            return date.fromisoformat(str(value))
        except (TypeError, ValueError):
            raise DocentesError(422, "INVALID", MSG_VALOR_INVALIDO) from None

    def alta(self, record: SessionRecord, data: dict) -> dict:
        scope = self.scope(record)
        apellido, nombres = _text(data.get("apellido")), _text(data.get("nombres"))
        email = _text(data.get("email"))
        cuil_limpio = rules.limpiar_cuil(_text(data.get("cuil")))
        nivel = _text(data.get("nivel_posgrado_salarial"))
        if nivel not in rules.NIVELES_POSGRADO_SALARIAL:
            raise DocentesError(422, "INVALID", MSG_VALOR_INVALIDO)
        antiguedad = self._antiguedad(data.get("antiguedad_anios"))
        fecha_alta = self._fecha(data.get("fecha_alta")) if data.get("fecha_alta") not in (None, "") else self.today()

        # Rama de la pantalla certificada: el boton "Guardar docente propio" solo existe sin coincidencias.
        def branch(repo: DocentesRepository) -> dict:
            otros = repo.mismo_cuil_otro_departamento(rules.clave_cuil(cuil_limpio)) if cuil_limpio.strip() else []
            local = repo.docente_existe(rules.clave_cuil(cuil_limpio)) if cuil_limpio else None
            return {"otros": otros, "local": local, "abierto": repo.open_period()}
        screen = self._read(scope, branch)
        if screen["otros"]:
            raise DocentesError(409, "CUIL_OTRO_DEPARTAMENTO", MSG_OTRO_DEPTO)
        if screen["local"] is not None:
            local = screen["local"]
            nombre_local = local.get("nombre") or cuil_limpio
            raise DocentesError(409, "CUIL_LOCAL", f"Este CUIL ya está registrado en el departamento actual como "
                                                   f"{nombre_local}.")
        problema = rules.problema_alta_docente(cuil_limpio, email)
        if not apellido or not nombres or not cuil_limpio:
            raise DocentesError(422, "REQUIRED", MSG_ALTA_REQUERIDOS)
        if problema:
            raise DocentesError(422, "INVALID", problema)

        nombre_generado = rules.nombre_completo(apellido, nombres)
        observaciones = _text(data.get("observaciones"))
        values = self._docente_values(cuil_limpio, apellido, nombres, _text(data.get("legajo")),
                                      _text(data.get("titulo")), _text(data.get("titulo_posgrado")), email,
                                      _text(data.get("telefono")), _text(data.get("ref_legajo_fisico")), "Activo",
                                      "Propio", fecha_alta, observaciones, antiguedad, nivel)
        abierto = screen["abierto"]
        self._writer(record, scope, W_GUARDAR, self._guardar_body(values), entity_raw=cuil_limpio, prefix=PREFIX_ALTA)
        self._movement(record, scope, tipo=MOV_ALTA, cuil=cuil_limpio, nombre=nombre_generado,
                       detalle="Se registró el docente en la base maestra.", observaciones=observaciones,
                       period_id=int(abierto["id"]) if abierto else None, prefix=PREFIX_ALTA)
        return {"mensaje": MSG_ALTA_OK, "tono": "success"}

    # ------------------------------------------------------------------ Edicion (actualizar_docente v168)
    def editar(self, record: SessionRecord, data: dict) -> dict:
        scope = self.scope(record)
        cuil_sel = data.get("cuil_original")
        base = self._read(scope, self._base_maestra)
        fila = self._row(base, cuil_sel)
        nuevo = {k: _text(data.get(k)) for k in ("apellido", "nombres", "cuil", "legajo", "titulo", "titulo_posgrado",
                                                 "email", "telefono", "ref_legajo_fisico", "observaciones")}
        nuevo_estado, nuevo_tipo = _text(data.get("estado")), _text(data.get("tipo_docente"))
        if nuevo_estado not in rules.ESTADOS_DOCENTE or nuevo_tipo not in rules.TIPOS_DOCENTE:
            raise DocentesError(422, "INVALID", MSG_VALOR_INVALIDO)
        antiguedad = self._antiguedad(data.get("antiguedad_anios"))
        nivel = data.get("nivel_posgrado_salarial")
        stale = self._stale_check(scope, cuil_sel, data.get("huella"))
        if fila is not None:
            problema = rules.problema_edicion_docente(fila["cuil"], nuevo["cuil"], fila.get("email"), nuevo["email"])
            if problema:
                raise DocentesError(422, "INVALID", problema)
        cuil_sel = str(cuil_sel or "")
        estado_anterior = (fila or {}).get("estado") or "Activo"

        def body(repo: DocentesRepository) -> dict:
            return identidad.actualizar_docente(
                repo, cuil_sel, nuevo["cuil"], nuevo["apellido"], nuevo["nombres"], nuevo["legajo"], nuevo["titulo"],
                nuevo["titulo_posgrado"], nuevo["email"], nuevo["telefono"], nuevo["ref_legajo_fisico"], nuevo_estado,
                nuevo_tipo, nuevo["observaciones"], antiguedad_anios=antiguedad, nivel_posgrado_salarial=nivel)

        resumen = self._writer(record, scope, W_ACTUALIZAR, body, entity_raw=nuevo["cuil"], stale=stale)
        nombre = rules.nombre_completo(nuevo["apellido"], nuevo["nombres"])
        abierto = base["abierto"]
        period_id = int(abierto["id"]) if abierto else None
        if estado_anterior not in rules.ESTADOS_BAJA_DOCENTE and nuevo_estado in rules.ESTADOS_BAJA_DOCENTE:
            tipo, detalle = MOV_BAJA, f"Se cambió el estado del docente de {estado_anterior} a {nuevo_estado}."
        elif estado_anterior in rules.ESTADOS_BAJA_DOCENTE and nuevo_estado == "Activo":
            tipo, detalle = MOV_ALTA, f"Se reactivó el docente. Estado anterior: {estado_anterior}."
        else:
            tipo, detalle = MOV_EDICION, "Se modificaron datos del docente en la base maestra."
        self._movement(record, scope, tipo=tipo, cuil=nuevo["cuil"], nombre=nombre, detalle=detalle,
                       period_id=period_id)
        if rules.limpiar_cuil(cuil_sel) != rules.limpiar_cuil(nuevo["cuil"]):
            mensaje = (f"{MSG_EDIT_OK} Se migraron {int(resumen.get('actualizados', 0) or 0)} referencia/s "
                       f"y se eliminaron {int(resumen.get('duplicados_eliminados', 0) or 0)} duplicado/s del CUIL "
                       "anterior.")
        else:
            mensaje = MSG_EDIT_OK
        return {"mensaje": mensaje, "tono": "success", "cuil": rules.limpiar_cuil(nuevo["cuil"])}

    # ------------------------------------------------------------------ Eliminacion fisica (eliminar_docente)
    def eliminar(self, record: SessionRecord, data: dict) -> dict:
        scope = self.scope(record)
        cuil_sel = str(data.get("cuil") or "")
        if data.get("confirmar") is not True:
            raise DocentesError(422, "CONFIRMATION_REQUIRED", MSG_ELIMINAR_CONFIRMAR)
        # La casilla "integral" solo existe en la pantalla cuando hay cargas locales.
        total_refs = self._read(scope, lambda repo: self._referencias(repo, cuil_sel)["total"])
        integral = data.get("integral") is True and total_refs > 0
        stale = self._stale_check(scope, cuil_sel, data.get("huella"))

        def body(repo: DocentesRepository) -> dict:
            clave = rules.clave_cuil(cuil_sel)
            if not clave:
                raise DocentesError(422, "INVALID", MSG_CUIL_SELECCION_INVALIDO)
            refs = self._referencias(repo, cuil_sel)
            if refs["total"] > 0 and not integral:
                raise DocentesError(409, "HAS_REFERENCES", (
                    "El docente todavía tiene cargas vinculadas en este departamento: "
                    f"{len(refs['designaciones'])} designación/es, "
                    f"{len(refs['comisiones'])} asignación/es en comisiones y "
                    f"{len(refs['investigacion'])} asignación/es de investigación y "
                    f"{len(refs['extension'])} asignación/es de extensión y "
                    f"{len(refs['actividades_especiales'])} participación/es en actividades especiales. "
                    "Revisá el detalle o activá la eliminación integral por error."))
            resumen = {k: 0 for k in ("designaciones", "comisiones", "investigacion", "extension",
                                      "actividades_especiales", "horarios_asignacion", "movimientos",
                                      "estados_consulta", "parametros_disposicion",
                                      "datos_disposicion_designaciones", "docentes")}
            ids_designaciones = [int(d["id"]) for d in refs["designaciones"] if d.get("id") is not None]
            if integral:
                ids_asig = [int(a["id"]) for a in refs["comisiones"] if a.get("id") is not None]
                if ids_asig:
                    resumen["horarios_asignacion"] = repo.delete_horarios_asignacion(ids_asig)
                if ids_designaciones:
                    resumen["datos_disposicion_designaciones"] = repo.delete_disposicion_designaciones(
                        ids_designaciones)
                resumen["comisiones"] = repo.delete_by_cuil("asignaciones_docentes_comision", clave)
                resumen["investigacion"] = repo.delete_by_cuil("investigacion_docente", clave)
                resumen["extension"] = repo.delete_by_cuil("extension_docente", clave)
                resumen["actividades_especiales"] = repo.delete_by_cuil("actividad_especial_docente", clave)
                resumen["designaciones"] = repo.delete_by_cuil("designaciones", clave)
            # Datos auxiliares locales que no deben quedar asociados a una carga eliminada por error.
            resumen["estados_consulta"] = repo.delete_by_cuil("estado_consulta_designacion", clave)
            resumen["parametros_disposicion"] = repo.delete_by_cuil("disposicion_docente_parametros", clave)
            resumen["movimientos"] = repo.delete_by_cuil("movimientos", clave)
            resumen["docentes"] = repo.delete_by_cuil("docentes", clave)
            if resumen["docentes"] == 0:
                raise DocentesError(409, "NOT_LOCAL", MSG_ELIMINAR_NO_LOCAL)
            return resumen

        res = self._writer(record, scope, W_ELIMINAR, body, entity_raw=cuil_sel, stale=stale)
        return {"mensaje": ("Docente eliminado únicamente del departamento actual. "
                            f"Se eliminaron {res.get('designaciones', 0)} designación/es, "
                            f"{res.get('comisiones', 0)} asignación/es en comisiones y "
                            f"{res.get('investigacion', 0)} asignación/es de investigación. "
                            "Para una baja real, debe cambiarse el estado del docente."),
                "tono": "warning", "resumen": res}

    # ------------------------------------------------------------------ Alta como prestado (v174)
    def _guardar_local_desde_existente(self, record: SessionRecord, scope: Scope, fila: dict, tipo: str,
                                       obs: str, stale: Optional[Callable[[], None]] = None) -> bool:
        """``_guardar_docente_local_desde_registro_existente`` (entry l. 23965)."""
        cuil = str(fila.get("cuil") or "").strip()
        if not cuil:
            return False
        if self._read(scope, lambda repo: repo.docente_existe(rules.clave_cuil(cuil))) is not None:
            return False
        antig = fila.get("antiguedad_anios")
        antiguedad = (None if rules._is_na(antig) else int(antig)) if antig is not None else None
        values = self._docente_values(
            cuil, str(fila.get("apellido") or ""), str(fila.get("nombres") or ""), str(fila.get("legajo") or ""),
            str(fila.get("titulo") or ""), str(fila.get("titulo_posgrado") or ""), str(fila.get("email") or ""),
            str(fila.get("telefono") or ""), str(fila.get("ref_legajo_fisico") or ""), "Activo", tipo,
            self.today(), obs, antiguedad, str(fila.get("nivel_posgrado_salarial") or ""))
        self._writer(record, scope, W_GUARDAR, self._guardar_body(values), entity_raw=cuil, stale=stale)
        return True

    # ------------------------------------------------------------------ E4-08: propio desde un registro existente
    def cuil_existente(self, record: SessionRecord, cuil_origen: Any, departamento_origen: Any,
                       cuil_alta: Any) -> dict:
        """Pantalla del camino "Registrar como propio y cargar una designación en el período actual" (entry
        l. 60247-60271): la coincidencia elegida de ``get_docentes_mismo_cuil_otro_departamento``, la ficha local
        (``docente_existe``) y el CUIL canonico.  Lectura fresca; la seleccion debe seguir entre las coincidencias."""
        scope = self.scope(record)
        self._require_read(record)
        cuil_limpio = rules.limpiar_cuil(_text(cuil_alta))
        origen_cuil, origen_dep = _text(cuil_origen), _text(departamento_origen)

        def screen(repo: DocentesRepository) -> dict:
            otros = repo.mismo_cuil_otro_departamento(rules.clave_cuil(cuil_limpio)) if cuil_limpio.strip() else []
            fila = next((r for r in otros if str(r.get("cuil") or "") == origen_cuil
                         and str(r.get("departamento_origen") or "") == origen_dep), None)
            local = repo.docente_existe(rules.clave_cuil(cuil_limpio)) if cuil_limpio else None
            return {"fila": fila, "local": local}

        s = self._read(scope, screen)
        fila, local = s["fila"], s["local"]
        if fila is None:
            raise DocentesError(409, "ORIGIN_NOT_FOUND", MSG_ORIGEN_NO_ENCONTRADO)
        canonico = str(((local or {}).get("cuil") if local is not None else fila.get("cuil")) or cuil_limpio).strip()
        return {"fila": fila, "local": local, "canonico": canonico, "nombre": str(fila.get("nombre_completo") or ""),
                "origen": str(fila.get("departamento_origen") or "otro departamento")}

    def guardar_propio_desde_existente(self, record: SessionRecord, seleccion: dict,
                                       stale: Optional[Callable[[], None]] = None) -> bool:
        """Alta local del docente compartido (entry l. 60329-60334): solo si no habia ficha local, con
        ``_guardar_docente_local_desde_registro_existente(fila, "Propio", "Docente compartido: mismo CUIL registrado
        en {origen}.")``.  ``seleccion`` es la de ``cuil_existente`` (servidor).  Devuelve si escribio."""
        if seleccion.get("local") is not None:
            return False
        obs = f"Docente compartido: mismo CUIL registrado en {seleccion['origen']}."
        return self._guardar_local_desde_existente(record, self.scope(record), seleccion["fila"], "Propio", obs,
                                                   stale=stale)

    # ------------------------------------------------------------------ E4-09: carga rapida integral (por fila)
    def alta_desde_carga_integral(self, record: SessionRecord, fila: dict, period_id: Optional[int]) -> None:
        """Paso 1 de la carga integral (entry l. 61471-61493): ``guardar_docente`` (propio, fecha de alta = hoy) +
        ``registrar_movimiento("Alta de docente", …, "Se registró el docente mediante el Excel integral.")``, dos
        COMMITs.  ``fila`` es la fila ya revisada por ``analizar_carga_integral_docentes_designaciones`` (servidor)."""
        scope = self.scope(record)
        cuil = rules.limpiar_cuil(fila.get("cuil", ""))
        antig = fila.get("antiguedad_anios")
        values = self._docente_values(
            cuil, fila.get("apellido", ""), fila.get("nombres", ""), fila.get("legajo", ""), fila.get("titulo", ""),
            fila.get("titulo_posgrado", ""), fila.get("email", ""), fila.get("telefono", ""),
            fila.get("ref_legajo_fisico", ""), fila.get("estado", "Activo"), observaciones=fila.get("observaciones", ""),
            antiguedad_anios=int(antig) if antig != "" and antig is not None else None,
            nivel_posgrado_salarial=fila.get("nivel_posgrado_salarial", ""))
        self._writer(record, scope, W_GUARDAR, self._guardar_body(values), entity_raw=cuil)
        self._movement(record, scope, tipo=MOV_ALTA, cuil=cuil,
                       nombre=rules.nombre_completo(fila.get("apellido", ""), fila.get("nombres", "")),
                       detalle="Se registró el docente mediante el Excel integral.",
                       observaciones=fila.get("observaciones", ""), period_id=period_id)

    def actualizar_desde_carga_integral(self, record: SessionRecord, cuil_original: str, datos: dict, campos: list,
                                        nombre: str, observaciones: str, period_id: Optional[int]) -> None:
        """Paso 5 de la carga integral (entry l. 61578-61604): ``actualizar_docente(cuil_original, cuil_original,
        …)`` con los datos mezclados por ``_mezclar_docente_existente_excel_v247`` + ``registrar_movimiento(
        "Actualización de docente existente", …)``, dos COMMITs."""
        scope = self.scope(record)

        def body(repo: DocentesRepository) -> dict:
            return identidad.actualizar_docente(
                repo, cuil_original, cuil_original, datos["apellido"], datos["nombres"], datos["legajo"],
                datos["titulo"], datos["titulo_posgrado"], datos["email"], datos["telefono"],
                datos["ref_legajo_fisico"], datos["estado"], datos["tipo_docente"], datos["observaciones"],
                antiguedad_anios=datos.get("antiguedad_anios"),
                nivel_posgrado_salarial=datos.get("nivel_posgrado_salarial", ""))

        self._writer(record, scope, W_ACTUALIZAR, body, entity_raw=cuil_original)
        self._movement(record, scope, tipo=MOV_ACTUALIZACION, cuil=cuil_original, nombre=nombre,
                       detalle="Se actualizaron mediante el Excel integral únicamente los campos informados: "
                               f"{', '.join(campos)}.", observaciones=observaciones, period_id=period_id)

    def prestado(self, record: SessionRecord, data: dict) -> dict:
        scope = self.scope(record)
        flujo = data.get("flujo")
        if flujo not in ("selector", "cuil_existente"):
            raise DocentesError(422, "INVALID", MSG_VALOR_INVALIDO)
        cuil_origen, dep_origen = _text(data.get("cuil")), _text(data.get("departamento_origen"))
        cuil_limpio = rules.limpiar_cuil(_text(data.get("cuil_alta")))

        def screen(repo: DocentesRepository) -> dict:
            if flujo == "selector":
                candidatos = repo.prestables()
                local_clave = None
            else:
                candidatos = repo.mismo_cuil_otro_departamento(rules.clave_cuil(cuil_limpio)) \
                    if cuil_limpio.strip() else []
                local_clave = rules.clave_cuil(cuil_limpio) if cuil_limpio else None
            fila = next((r for r in candidatos if str(r.get("cuil") or "") == cuil_origen
                         and str(r.get("departamento_origen") or "") == dep_origen), None)
            if fila is None:
                return {"fila": None}
            if flujo == "selector":
                local = repo.docente_existe(rules.clave_cuil(str(fila.get("cuil") or "").strip()))
            else:
                local = repo.docente_existe(local_clave) if local_clave else None
            return {"fila": fila, "local": local, "abierto": repo.open_period(), "actual": repo.last_period()}

        s = self._read(scope, screen)
        fila = s["fila"]
        if fila is None:
            raise DocentesError(409, "ORIGIN_NOT_FOUND", MSG_ORIGEN_NO_ENCONTRADO)
        abierto, local = s["abierto"], s["local"]
        origen = str(fila.get("departamento_origen") or "otro departamento")
        obs = f"Docente prestado desde {origen}. No posee designación local en este departamento."
        nombre = str(fila.get("nombre_completo") or "")
        if not abierto:
            raise DocentesError(409, "NO_OPEN_PERIOD", MSG_SIN_PERIODO_PRESTAMO)
        per_nombre, per_id = abierto["nombre"], int(abierto["id"])
        historico = bool(s["actual"] and int(s["actual"]["id"]) != per_id)
        fecha_desde = rules.safe_date(abierto.get("fecha_inicio"), self.today()) if historico else self.today()

        if flujo == "selector":
            cuil_p = str(fila.get("cuil") or "").strip()
            if local is not None:
                if str(local.get("tipo_docente") or "Propio") != "Prestado":
                    raise DocentesError(409, "PROPIO_LOCAL", MSG_PROPIO_LOCAL)
                res = self._writer(record, scope, W_PRESTAMO, self._prestamo_body(cuil_p, per_id, origen, obs,
                                                                                  fecha_desde), entity_raw=cuil_p)
                if not res.get("cambio"):
                    return {"mensaje": f"Este docente ya tiene un préstamo activo en {per_nombre}.", "tono": "info"}
                self._movement(record, scope, tipo=MOV_ALTA_PRESTADO, cuil=cuil_p, nombre=nombre,
                               detalle=f"Se registró el préstamo desde {origen} exclusivamente para {per_nombre}.",
                               observaciones=obs, period_id=per_id)
                return {"mensaje": f"Préstamo registrado para {per_nombre}. No se trasladará automáticamente al "
                                   "período siguiente.", "tono": "success"}
            self._guardar_local_desde_existente(record, scope, fila, "Prestado", obs)
            self._writer(record, scope, W_PRESTAMO, self._prestamo_body(cuil_p, per_id, origen, obs, fecha_desde),
                         entity_raw=cuil_p)
            self._movement(record, scope, tipo=MOV_ALTA_PRESTADO, cuil=cuil_p, nombre=nombre,
                           detalle=f"Se incorporó como prestado desde {origen} exclusivamente para {per_nombre}, "
                                   "sin designación local.", observaciones=obs, period_id=per_id)
            return {"mensaje": f"Docente prestado registrado para {per_nombre}. No se trasladará automáticamente al "
                               "período siguiente.", "tono": "success"}

        # Flujo "CUIL ya registrado en otro departamento" del formulario de alta.
        canonico = str(((local or {}).get("cuil") if local is not None else fila.get("cuil")) or cuil_limpio).strip()
        if local is not None and str(local.get("tipo_docente") or "Propio").strip() != "Prestado":
            raise DocentesError(409, "YA_PROPIO", MSG_YA_PROPIO)
        if local is None:
            self._guardar_local_desde_existente(record, scope, fila, "Prestado", obs)
        res = self._writer(record, scope, W_PRESTAMO, self._prestamo_body(canonico, per_id, origen, obs, fecha_desde),
                           entity_raw=canonico)
        if not res.get("cambio"):
            return {"mensaje": f"Este docente ya tiene un préstamo activo en {per_nombre}.", "tono": "info"}
        self._movement(record, scope, tipo=MOV_ALTA_PRESTADO, cuil=canonico, nombre=nombre,
                       detalle=f"Se incorporó como prestado desde {origen} exclusivamente para {per_nombre}, "
                               "sin designación local.", observaciones=obs, period_id=per_id)
        return {"mensaje": f"Docente incorporado como prestado para {per_nombre}. El préstamo vence con ese período.",
                "tono": "success"}

    # ------------------------------------------------------------------ Finalizar prestamo (v174)
    def finalizar_prestamo(self, record: SessionRecord, data: dict) -> dict:
        scope = self.scope(record)
        cuil_sel = str(data.get("cuil") or "")

        def screen(repo: DocentesRepository) -> dict:
            base = self._base_maestra(repo)
            fila = self._row(base, cuil_sel)
            abierto = base["abierto"]
            activo = self._prestamo_activo(repo, int(abierto["id"]), cuil_sel) if fila and abierto else None
            return {"fila": fila, "abierto": abierto, "activo": activo}

        s = self._read(scope, screen)
        fila, abierto = s["fila"], s["abierto"]
        if fila is None:
            raise DocentesError(404, "NOT_FOUND", MSG_DOCENTE_NO_ENCONTRADO)
        if str(fila.get("tipo_docente") or "Propio").strip() != "Prestado" or not abierto:
            raise DocentesError(409, "NOT_LOAN", MSG_VALOR_INVALIDO)
        per_nombre, per_id = abierto["nombre"], int(abierto["id"])
        if s["activo"] is None:
            raise DocentesError(409, "NO_ACTIVE_LOAN", (
                f"Este docente no tiene un préstamo activo en {per_nombre}. Si vuelve a ser prestado, registralo "
                "nuevamente desde 'Registrar docente'."))
        fecha = self._fecha(data.get("fecha_fin")) if data.get("fecha_fin") not in (None, "") else self.today()
        obs = _text(data.get("observaciones"))
        if data.get("confirmar") is not True:
            raise DocentesError(422, "CONFIRMATION_REQUIRED", MSG_FIN_CONFIRMAR)
        stale = self._stale_check(scope, cuil_sel, data.get("huella"))

        def body(repo: DocentesRepository) -> dict:
            if self._prestamo_activo(repo, per_id, cuil_sel) is None:
                return {"cambio": False, "asignaciones_finalizadas": 0}
            n = repo.finalizar_prestamo(period_id=per_id, cuil=cuil_sel, fecha_hasta=str(fecha), observaciones=obs,
                                        fecha_finalizacion=self.now().isoformat(timespec="seconds"))
            return {"cambio": True, "asignaciones_finalizadas": n}

        res = self._writer(record, scope, W_FIN_PRESTAMO, body, entity_raw=cuil_sel, stale=stale)
        if not res.get("cambio"):
            return {"mensaje": MSG_FIN_SIN_CAMBIO, "tono": "info"}
        self._movement(record, scope, tipo=MOV_FIN_PRESTAMO, cuil=cuil_sel, nombre=fila.get("nombre_completo", ""),
                       detalle=(f"Finalizó el préstamo recibido en {per_nombre} el {fecha}. "
                                f"Asignaciones en comisión finalizadas: {res.get('asignaciones_finalizadas', 0)}."),
                       observaciones=obs, period_id=per_id)
        return {"mensaje": MSG_FIN_OK, "tono": "success"}

    # ------------------------------------------------------------------ Reparar CUIL huerfano (v168)
    def reparar_cuil(self, record: SessionRecord, data: dict) -> dict:
        scope = self.scope(record)
        cuil_sel, huerfano = str(data.get("cuil") or ""), _text(data.get("cuil_huerfano"))

        def screen(repo: DocentesRepository) -> dict:
            base = self._base_maestra(repo)
            return {"fila": self._row(base, cuil_sel),
                    "huerfanos": [h["cuil_huerfano"] for h in identidad.cuiles_huerfanos(repo)]}

        s = self._read(scope, screen)
        if s["fila"] is None:
            raise DocentesError(404, "NOT_FOUND", MSG_DOCENTE_NO_ENCONTRADO)
        if huerfano not in s["huerfanos"]:
            raise DocentesError(409, "STALE", f"{MSG_STALE} [B12I: get_cuiles_huerfanos_v168]")
        if data.get("confirmar") is not True:
            raise DocentesError(422, "CONFIRMATION_REQUIRED", MSG_REPARAR_CONFIRMAR)
        nombre = s["fila"].get("nombre_completo", "")
        stale = self._stale_check(scope, cuil_sel, data.get("huella"))
        res = self._writer(record, scope, W_MIGRAR,
                           lambda repo: identidad.migrar_referencias_cuil(repo, huerfano, cuil_sel, nombre),
                           prefix=PREFIX_REPARAR, stale=stale)
        return {"mensaje": (f"CUIL anterior reparado. Se migraron {int(res.get('actualizados', 0) or 0)} "
                            f"referencia/s y se eliminaron {int(res.get('duplicados_eliminados', 0) or 0)} "
                            "duplicado/s viejo/s. El CUIL anterior ya no queda asociado a ninguna carga conocida."),
                "tono": "success"}

    # ------------------------------------------------------------------ Carga rapida simple
    def _parse(self, texto: Any) -> list[dict]:
        try:
            return carga.filas_pegadas(texto)
        except Exception as exc:
            log.info("docentes: tabla pegada no interpretable: %s", type(exc).__name__)
            raise DocentesError(422, "PARSE", MSG_CARGA_SIN_FILAS) from None

    @staticmethod
    def _duplicados(repo: DocentesRepository, filas: list[dict]) -> list[dict]:
        """``detectar_docentes_duplicados_carga``."""
        out, vistos = [], set()
        for idx, row in enumerate(filas):
            cuil = rules.limpiar_cuil(row.get("cuil", ""))
            en_pegado = cuil in vistos
            vistos.add(cuil)
            existe = repo.docente_existe(rules.clave_cuil(cuil)) is not None if cuil else False
            if en_pegado or existe:
                out.append({"fila_pegada": idx + 1, "cuil": cuil, "apellido": row.get("apellido", ""),
                            "nombres": row.get("nombres", ""),
                            "motivo": "Duplicado dentro de la tabla pegada" if en_pegado
                            else "Ya existe en la base maestra"})
        return out

    def carga_preview(self, record: SessionRecord, texto: Any) -> dict:
        scope = self.scope(record)
        self._require_read(record)
        filas = self._parse(texto)
        if not filas:
            aviso = MSG_CARGA_SIN_FILAS if str(texto or "").strip() else None
            return {"filas": [], "duplicados": [], "aviso": aviso}
        dups = self._read(scope, lambda repo: self._duplicados(repo, filas))
        return {"filas": filas, "duplicados": dups, "aviso": None}

    def carga_ejecutar(self, record: SessionRecord, texto: Any, confirmar: Any) -> dict:
        scope = self.scope(record)
        filas = self._parse(texto)
        if not filas:
            raise DocentesError(422, "PARSE", MSG_CARGA_SIN_FILAS)
        s = self._read(scope, lambda repo: {"dups": self._duplicados(repo, filas), "abierto": repo.open_period()})
        hay_dup = bool(s["dups"])
        if hay_dup and confirmar is not True:
            raise DocentesError(422, "DUPLICATES", MSG_CARGA_DUPLICADOS)
        actualizar_existentes = hay_dup and confirmar is True
        period_id = int(s["abierto"]["id"]) if s["abierto"] else None
        cargados = actualizados = omitidos = 0
        vistos: set[str] = set()
        for pos, row in enumerate(filas, start=1):
            try:
                cuil_row = rules.limpiar_cuil(row.get("cuil", ""))
                if not cuil_row or cuil_row in vistos:
                    omitidos += 1
                    continue
                vistos.add(cuil_row)
                v = {k: rules.limpiar_texto_tabla(row.get(k, "")) for k in (
                    "apellido", "nombres", "legajo", "titulo", "titulo_posgrado", "email", "telefono",
                    "ref_legajo_fisico", "estado", "observaciones")}
                estado_row = v["estado"] or "Activo"
                nombre_row = rules.nombre_completo(v["apellido"], v["nombres"])
                existe = self._read(scope, lambda repo: repo.docente_existe(rules.clave_cuil(cuil_row))) is not None
                if existe:
                    if actualizar_existentes:
                        self._writer(record, scope, W_ACTUALIZAR, lambda repo: identidad.actualizar_docente(
                            repo, cuil_row, cuil_row, v["apellido"], v["nombres"], v["legajo"], v["titulo"],
                            v["titulo_posgrado"], v["email"], v["telefono"], v["ref_legajo_fisico"], estado_row,
                            "Propio", v["observaciones"]), entity_raw=cuil_row)
                        self._movement(record, scope, tipo=MOV_ACTUALIZACION, cuil=cuil_row, nombre=nombre_row,
                                       detalle="Se actualizó el docente mediante carga rápida.",
                                       observaciones=v["observaciones"], period_id=period_id)
                        actualizados += 1
                    else:
                        omitidos += 1
                else:
                    values = self._docente_values(cuil_row, v["apellido"], v["nombres"], v["legajo"], v["titulo"],
                                                  v["titulo_posgrado"], v["email"], v["telefono"],
                                                  v["ref_legajo_fisico"], estado_row, observaciones=v["observaciones"])
                    self._writer(record, scope, W_GUARDAR, self._guardar_body(values), entity_raw=cuil_row)
                    self._movement(record, scope, tipo=MOV_ALTA, cuil=cuil_row, nombre=nombre_row,
                                   detalle="Se registró el docente mediante carga rápida.",
                                   observaciones=v["observaciones"], period_id=period_id)
                    cargados += 1
            except DocentesError as exc:
                # El certificado no captura la excepcion: las filas anteriores quedan confirmadas.
                raise DocentesError(exc.status, exc.code, (
                    f"La carga se interrumpió en la fila {pos}: {exc.message} Filas ya procesadas antes del error: "
                    f"nuevos {cargados}, actualizados {actualizados}, omitidos {omitidos}."), exc.error_class) from None
        return {"mensaje": f"Carga finalizada. Nuevos: {cargados}. Actualizados: {actualizados}. Omitidos: {omitidos}.",
                "tono": "success"}
