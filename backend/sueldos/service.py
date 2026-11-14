"""Reglas de pantalla de Sueldos (B13-FIX02, entry l. 61762-61931) sobre la sesion y el contexto de ``auth``.

Alcance (decisiones H1-H12, docs/sueldos_analysis.md §29-§30): las 3 pestañas certificadas y su unico writer.
No existen (y no se agregan) Excel, importacion, exportacion, carga rapida, eliminacion de escalas ni movimientos (H10).

Ambito:
- "⚙️ Escalas básicas" y "📈 Tabla salarial": INSTITUCION de la sesion revalidada (``escalas_salariales_docentes`` es
  institucional); funcionan aunque la sesion no tenga departamento (superadmin en una institucion sin departamentos).
- "👥 Sueldos del plantel": DEPARTAMENTO de la sesion (``get_designaciones`` / ``get_docentes`` / ``get_periodos``); sin
  departamento -> aviso de ambito institucional (como los demas modulos departamentales de NEXT).

El writer ``guardar_escala_salarial_v256`` es una operacion B12H propia (``correlation_id`` por clic):
1. B10 ``sueldos.write`` con alcance INSTITUCION (superadmin y usuario_departamento: ALLOW; coordinador, solo
   lectura y modo comercial read_only: DENY) -> DENIED en transaccion propia (H11: permiso certificado mantenido);
2. B12I: SIN lock de capa T (ninguna familia lo incluye) y SIN revalidacion de capa U ni huella (las lecturas de
   escalas no tienen cache certificada; el guardado es un UPSERT completo) (H6);
3. 1 COMMIT con los 6 UPSERT y su SUCCESS ``IN_TRANSACTION`` (``commit_seq`` 1); ``ValueError`` del writer -> FAILED
   ``ValueError`` y ROLLBACK de todo; error de base -> FAILED (B12D).
``usuario_actualizacion`` = nombre o email del usuario de la SESION (H5): nunca un valor enviado por el cliente.

Helpers internos sin endpoint ni pantalla (Etapa 4, H2/H3): ``sueldo_docente_resumen`` (seccion "💰 Sueldo estimado"
del Resumen docente) y ``costos_proyectos_vigentes`` (costos v257/v258 de Investigacion/Extension).
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
from auth import policy
from auth.service import AuthService, SessionRecord
from comisiones.service import _jsonable, _period, records
from periodos.service import MSG_DB_READ, MSG_DB_TRANSACTION, MSG_INSTITUTIONAL, denial_message, scope_message

from . import escrituras as E
from . import rules as SR
from .lecturas import Motor, costos_por_proyecto, ficha_salarial
from .repository import SueldosRepository

log = logging.getLogger("deptit_next.sueldos")

MODULO = "sueldos"
INST = policy.SCOPE_INSTITUTION
ACTION_READ = policy.Action(MODULO, policy.OP_READ, INST)
ACTION_WRITE = policy.Action(MODULO, policy.OP_WRITE, INST)


@dataclass(frozen=True)
class WriterSpec:
    """Writer del registro B10 (legacy_write_actions.py l. 229) y su etiqueta B12H (``entity_type_for`` /
    ``_entity_param`` certificados: docs/audit/sueldos_phase_a/b10_b12h_sueldos.txt): sin parametro ``*_id``."""
    name: str
    action: policy.Action
    entity_type: str
    entity_param: Optional[str]


SPEC_GUARDAR_ESCALA = WriterSpec(E.W_GUARDAR_ESCALA, ACTION_WRITE, "escala_salarial", None)

# --- textos certificados (entry l. 61762-61931) ----------------------------------------------------------------
INFO_PAGINA = ("Configurá el básico mensual de la dedicación **Simple** para cada cargo. La app calcula automáticamente "
               "Parcial/Semiexclusiva ×2, Parcial + Simple ×3, Exclusiva ×4 y Exclusiva + Simple ×5. Luego suma "
               "antigüedad y, si corresponde, el adicional por posgrado. Una designación Ad Honorem siempre computa $0.")
CAPTION_ESCALAS = ("Solo cargás los seis básicos Simple. Si el mes todavía no tiene una escala, se propone como referencia "
                   "la última escala anterior disponible. La tabla 06/2026 suministrada quedó precargada.")
MSG_SIN_ESCALAS = "Todavía no hay escalas salariales cargadas."
MSG_CARGA_PRIMERO = "Cargá primero una escala salarial."
AYUDA_DEDICACION = "Parcial equivale a la semiexclusiva indicada en la escala: ×2 del básico Simple."
TEXTO_ANTIGUEDAD = ("**Adicionales por antigüedad:** 0–4: 20% · 5–6: 30% · 7–9: 40% · 10–11: 50% · 12–14: 60% · "
                    "15–16: 70% · 17–19: 80% · 20–21: 100% · 22–23: 110% · 24+: 120%.")
TEXTO_POSGRADO = ("**Posgrado:** Especialista +5% · Magíster +8% · Doctor +18% del básico correspondiente a la "
                  "dedicación.")
MSG_SIN_PERIODOS = "No hay períodos registrados."
MSG_SIN_ESCALA_PERIODO = "No hay una escala salarial disponible para ese período."
MSG_SIN_DESIGNACIONES = "No hay designaciones registradas en el período seleccionado."
MSG_NADA_QUE_CALCULAR = "No hay designaciones para calcular."
CAPTION_PLANTEL = ("Estimación basada en básicos, dedicación, antigüedad y adicional por posgrado configurados. No "
                   "incorpora otros adicionales, descuentos ni conceptos de liquidación no modelados en la app.")
AYUDA_SIN_PERMISO = "Tu rol permite visualizar, pero no cargar, editar ni generar cambios."
MSG_VALOR_INVALIDO = "Uno de los valores enviados no es válido para este formulario."
MSG_SELECCION_INVALIDA = "La selección no corresponde a las filas mostradas. Actualizá la pantalla."
PREFIJO_ERROR = "No se pudo guardar la escala: "


class SueldosError(Exception):
    """Error controlado para la UI.  ``error_class`` = clase de la excepcion certificada equivalente (B12H)."""

    def __init__(self, status: int, code: str, message: str, error_class: str = "ValueError", tone: str = "error"):
        super().__init__(message)
        self.status, self.code, self.message, self.error_class, self.tone = status, code, message, error_class, tone


@dataclass(frozen=True)
class Scope:
    institution_id: int
    department_id: Optional[int]
    institution: dict
    department: Optional[dict]
    rol: Optional[str]


def _named(row: Optional[dict]) -> Optional[dict]:
    return None if row is None else {"id": int(row["id"]), "nombre": row.get("nombre")}


def _int(value: Any, lo: int, hi: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not lo <= value <= hi:
        raise SueldosError(422, "INVALID", MSG_VALOR_INVALIDO)
    return value


def _choice(value: Any, options: list) -> Any:
    if value not in options:
        raise SueldosError(422, "INVALID", MSG_VALOR_INVALIDO)
    return value


def _mes_ref(data: dict) -> str:
    """Selectores "Mes" (1-12) y "Año" (``number_input`` 2000-2100) de "⚙️ Escalas básicas" (l. 61778-61786)."""
    anio = _int(data.get("anio"), 2000, 2100)
    mes = _int(data.get("mes"), 1, 12)
    return f"{anio:04d}-{int(mes):02d}"


def _valores(raw: Any) -> dict:
    """6 ``number_input`` (``min_value=0.0``, ``format="%.2f"``): solo numeros finitos >= 0 de los cargos certificados."""
    if not isinstance(raw, dict):
        raise SueldosError(422, "INVALID", MSG_VALOR_INVALIDO)
    out = {}
    for cargo, v in raw.items():
        if cargo not in SR.CARGOS or isinstance(v, bool) or not isinstance(v, (int, float)) \
                or not math.isfinite(float(v)) or float(v) < 0:
            raise SueldosError(422, "INVALID", MSG_VALOR_INVALIDO)
        out[cargo] = float(v)
    return out


def _fecha_txt(value: Any) -> Optional[str]:
    """``fecha_actualizacion`` (timestamp) como la muestra ``st.dataframe``: ``AAAA-MM-DD HH:MM:SS``."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


class SueldosService:
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
        if resolution.institution is None or resolution.reason is not None:
            raise SueldosError(409, "SCOPE_NOT_VERIFIED", scope_message(resolution))
        if not any(m[0] == MODULO for m in visible):
            raise SueldosError(409, "SCOPE_INSTITUTIONAL", MSG_INSTITUTIONAL)
        actor = policy.actor_from_session(user, session_scope)
        dep = resolution.department
        return Scope(int(resolution.institution["id"]), int(dep["id"]) if dep is not None else None,
                     resolution.institution, dep, actor.role)

    def _require_read(self, record: SessionRecord) -> None:
        actor = policy.actor_from_session(record.user, record.scope)
        decision = policy.decide(actor, ACTION_READ)
        if not decision.allowed:
            raise SueldosError(403, "DENIED", denial_message(decision, ACTION_READ))

    def reader(self, record: SessionRecord) -> Scope:
        scope = self.scope(record)
        self._require_read(record)
        return scope

    def _read(self, scope: Scope, fn: Callable[[Motor], Any]) -> Any:
        try:
            with self._transaction() as conn:
                conn.execute("SET TRANSACTION READ ONLY")
                return fn(Motor(SueldosRepository(conn, scope.institution_id, scope.department_id), self.today()))
        except SueldosError:
            raise
        except Exception as exc:
            log.error("sueldos: lectura fallida: %s", type(exc).__name__)
            raise SueldosError(503, "DB_READ", MSG_DB_READ) from None

    def _puede_escribir(self, record: SessionRecord) -> bool:
        return policy.decide(policy.actor_from_session(record.user, record.scope), ACTION_WRITE).allowed

    # ------------------------------------------------------------------ B10 + B12H del writer (sin lock: H6)
    def _separate(self, op: audit.Operation, outcome: str, *, error_code: Optional[str] = None,
                  metadata: Optional[dict] = None) -> bool:
        mode = audit.MODE_POST_OPERATION if outcome == audit.OUTCOME_SUCCESS else audit.MODE_SEPARATE
        try:
            self.audit_store.append_separate(op.event(outcome, mode, error_code=error_code, metadata=metadata))
            return True
        except Exception as exc:
            log.error("B12H: el evento %s de %s no pudo persistirse (%s)", outcome, op.name, audit.error_code_of(exc))
            return False

    @staticmethod
    def _usuario(record: SessionRecord) -> str:
        """``current_user().get("nombre") or .get("email") or ""`` (l. 25633-25637) sobre el usuario revalidado."""
        try:
            u = record.user or {}
            return str(u.get("nombre") or u.get("email") or "")
        except Exception:
            return ""

    def _op(self, record: SessionRecord, scope: Scope, spec: WriterSpec, fn: Callable[[E.Unidad], Any]) -> Any:
        actor = policy.actor_from_session(record.user, record.scope)
        audit_actor = audit.actor_from_record(record.user, record.scope, record.meta)
        op = audit.Operation(spec.name, spec.action, spec.entity_type, audit_actor, spec.entity_param, None)
        decision = policy.decide(actor, spec.action)
        if not decision.allowed:
            self._separate(op, audit.OUTCOME_DENIED, error_code=decision.code, metadata={"b10_decision": decision.code})
            raise SueldosError(403, "DENIED", denial_message(decision, spec.action), "PermissionError")
        unidad = E.Unidad(self._transaction, op, scope.institution_id, scope.department_id, today=self.today(),
                          now=self.now(), usuario=self._usuario(record))
        try:
            result = fn(unidad)
        except ValueError as exc:
            self._separate(op, audit.OUTCOME_FAILED, error_code="ValueError",
                           metadata={"coupled_commits": op.coupled_commits})
            raise SueldosError(422, "REJECTED", f"{PREFIJO_ERROR}{exc}") from None
        except E.AuditoriaFallida:
            self._separate(op, audit.OUTCOME_FAILED, error_code="AuditPersistenceError:AUDIT_INSERT_FAILED",
                           metadata={"coupled_commits": op.coupled_commits})
            raise SueldosError(503, "AUDIT", f"{audit.MSG_PERSIST} [AUDIT_INSERT_FAILED]",
                               "AuditPersistenceError") from None
        except Exception as exc:
            log.error("sueldos: %s falló tras %d COMMIT(s): %s", spec.name, op.coupled_commits, type(exc).__name__)
            self._separate(op, audit.OUTCOME_FAILED, error_code=audit.error_code_of(exc),
                           metadata={"coupled_commits": op.coupled_commits})
            raise SueldosError(503, "DB_ERROR", f"{PREFIJO_ERROR}{MSG_DB_TRANSACTION}") from None
        return result

    # ------------------------------------------------------------------ overview (encabezado l. 61763-61772)
    def overview(self, record: SessionRecord) -> dict:
        scope = self.reader(record)
        hoy = self.today()
        plantel: dict[str, Any] = {"disponible": scope.department_id is not None}
        if scope.department_id is not None:
            def read(m: Motor):
                # ``opciones_per_s = {str(nombre): int(id)}`` (l. 61866): un nombre repetido conserva su primera
                # posicion y el id de la ultima fila; por defecto el abierto o el ultimo (``safe_index`` -> 0).
                opciones: dict[str, int] = {}
                for p in m.periodos():
                    opciones[str(p.get("nombre"))] = int(p.get("id"))
                defecto = m.periodo_abierto() or m.ultimo_periodo()
                nombre_def = str(defecto.get("nombre")) if defecto else (next(iter(opciones), None))
                return [{"nombre": k, "id": v} for k, v in opciones.items()], nombre_def
            periodos, defecto = self._read(scope, read)
            plantel.update({"periodos": periodos, "periodo_defecto": defecto if any(
                p["nombre"] == defecto for p in periodos) else (periodos[0]["nombre"] if periodos else None)})
        else:
            plantel["mensaje"] = MSG_INSTITUTIONAL
        puede = self._puede_escribir(record)
        return {
            "contexto": {"institucion": _named(scope.institution), "departamento": _named(scope.department)},
            "rol": scope.rol,
            "permisos": {"puede_escribir": puede},
            "ayuda_sin_permiso": None if puede else AYUDA_SIN_PERMISO,
            "info": INFO_PAGINA,
            "hoy": {"anio": int(hoy.year), "mes": int(hoy.month)},
            "meses": SR.MESES,
            "cargos": SR.CARGOS,
            "dedicaciones": SR.DEDICACIONES_TABLA,
            "niveles": SR.NIVELES_POSGRADO_SALARIAL_V256,
            "textos": {"caption_escalas": CAPTION_ESCALAS, "ayuda_dedicacion": AYUDA_DEDICACION,
                       "antiguedad": TEXTO_ANTIGUEDAD, "posgrado": TEXTO_POSGRADO, "caption_plantel": CAPTION_PLANTEL},
            "plantel": plantel,
        }

    # ------------------------------------------------------------------ Pestaña 1: ⚙️ Escalas básicas
    def escalas(self, record: SessionRecord, data: dict) -> dict:
        scope = self.reader(record)
        mes_ref = _mes_ref(data)

        def read(m: Motor):
            escala_mes = m.escala_mes(mes_ref)
            _, previa = m.escala_aplicable(mes_ref)
            valores = {c: SR.valor_inicial_formulario(c, escala_mes, previa) for c in SR.CARGOS}
            df = m.escalas()
            historico = []
            for _, r in df.iterrows():
                historico.append({
                    "Mes": SR.etiqueta_mes_v256(r.get("mes_referencia")),
                    "Cargo": r.get("cargo"),
                    "Básico Simple": SR.moneda_v256(pd.to_numeric(pd.Series([r.get("basico_simple")]),
                                                                  errors="coerce").fillna(0).iloc[0]),
                    "Última actualización": _fecha_txt(r.get("fecha_actualizacion")),
                    "Usuario": r.get("usuario_actualizacion"),
                })
            return {"mes_referencia": mes_ref, "etiqueta": SR.etiqueta_mes_v256(mes_ref), "valores": valores,
                    "historico": historico, "mensaje_historico": None if historico else MSG_SIN_ESCALAS}
        return self._read(scope, read)

    def guardar_escala(self, record: SessionRecord, data: dict) -> dict:
        """"💾 Guardar / actualizar escala mensual" (l. 61804-61810)."""
        scope = self.reader(record)
        mes_ref = _mes_ref(data)
        valores = _valores(data.get("valores"))
        self._op(record, scope, SPEC_GUARDAR_ESCALA, lambda u: E.guardar_escala_salarial_v256(u, mes_ref, valores))
        return {"mensaje": f"Escala {SR.etiqueta_mes_v256(mes_ref)} guardada correctamente.", "tono": "success"}

    # ------------------------------------------------------------------ Pestaña 2: 📈 Tabla salarial
    def tabla(self, record: SessionRecord, data: dict) -> dict:
        scope = self.reader(record)
        dedicacion = _choice(data.get("dedicacion") or "Simple", SR.DEDICACIONES_TABLA)
        nivel = _choice(data.get("nivel") if data.get("nivel") is not None else "", SR.NIVELES_POSGRADO_SALARIAL_V256)

        def read(m: Motor):
            meses = m.meses_disponibles()
            if not meses:
                return {"meses": [], "mensaje": MSG_CARGA_PRIMERO}
            mes = data.get("mes_referencia") or meses[0]
            if mes not in meses:
                raise SueldosError(409, "SELECCION", MSG_SELECCION_INVALIDA)
            escala = m.escala_mes(mes)
            caption = (f"Escala {SR.etiqueta_mes_v256(mes)} · {dedicacion} · "
                       f"{nivel or 'Sin adicional por posgrado'}. La antigüedad mínima (0 años) ya aplica 20%.")
            return {"meses": [{"valor": x, "etiqueta": SR.etiqueta_mes_v256(x)} for x in meses], "mes": mes,
                    "dedicacion": dedicacion, "nivel": nivel, "caption": caption,
                    "filas": SR.tabla_salarial_v256(escala, dedicacion, nivel)}
        return self._read(scope, read)

    # ------------------------------------------------------------------ Pestaña 3: 👥 Sueldos del plantel
    def plantel(self, record: SessionRecord, data: dict) -> dict:
        scope = self.reader(record)
        if scope.department_id is None:
            raise SueldosError(409, "SCOPE_INSTITUTIONAL", MSG_INSTITUTIONAL)
        pid = data.get("periodo_id")
        if isinstance(pid, bool) or not isinstance(pid, int):
            raise SueldosError(422, "INVALID", MSG_VALOR_INVALIDO)

        def read(m: Motor):
            periodos = m.periodos()
            if not periodos:
                return {"estado": "sin_periodos", "mensaje": MSG_SIN_PERIODOS, "tono": "info"}
            opciones: dict[str, int] = {}
            for p in periodos:
                opciones[str(p.get("nombre"))] = int(p.get("id"))
            fila = next((p for p in periodos if int(p["id"]) == pid), None)
            if fila is None or pid not in opciones.values():
                raise SueldosError(409, "SELECCION", MSG_SELECCION_INVALIDA)
            r = m.plantel(dict(fila))
            if r["estado"] == "sin_escala":
                return {"estado": "sin_escala", "mensaje": MSG_SIN_ESCALA_PERIODO, "tono": "warning"}
            base = {"caption_escala": f"Escala aplicada automáticamente: **{SR.etiqueta_mes_v256(r['mes_escala'])}**."}
            if r["estado"] == "sin_designaciones":
                return {"estado": r["estado"], **base, "mensaje": MSG_SIN_DESIGNACIONES, "tono": "info"}
            if r["estado"] == "vacio":
                return {"estado": r["estado"], **base, "mensaje": MSG_NADA_QUE_CALCULAR, "tono": "info"}
            filas = []
            for f in r["filas"]:
                g = dict(f)
                g["Básico dedicación"] = SR.moneda_v256(g["Básico dedicación"])
                g["Sueldo estimado"] = SR.moneda_v256(g["Sueldo estimado"])
                filas.append({k: _jsonable(v) for k, v in g.items()})
            return {"estado": "ok", **base, "metricas": {"docentes": r["docentes"], "designaciones": r["designaciones"],
                                                         "total": SR.moneda_v256(r["total"])},
                    "filas": filas, "caption": CAPTION_PLANTEL}
        return self._read(scope, read)

    # ------------------------------------------------------------------ helpers internos (Etapa 4; sin endpoint)
    def sueldo_docente_resumen(self, scope: Scope, cuil, periodo: dict) -> dict:
        """Seccion "💰 Sueldo estimado — {período}" del Resumen docente (l. 61008-61030) con la cadena certificada.

        Contrato: ``periodo`` = fila de ``get_periodos`` del departamento de la sesion.  Devuelve los montos SIN
        formatear y el formateo certificado aparte.  Las dos DEUDAS FUNCIONALES H2 que la Etapa 4 replicaba quedan
        CORREGIDAS en la Etapa 5 / Tanda B (B1; ``docs/ETAPA5_TANDA_B_CLOSE.md``):
        - la fuente v149 no traia ``ad_honorem`` y sumaba Suspendidas, Finalizadas y Bajas del periodo actual: ahora
          ``designaciones_sueldo_resumen`` (Ad Honorem $0; solo Activas en el periodo no cerrado, como la base
          certificada l. 26679 y el plantel);
        - el perfil salia de ``get_resumen_docente``, cuyo SELECT no trae ``antiguedad_anios`` ni
          ``nivel_posgrado_salarial`` (siempre 0 anios / sin posgrado): ahora se usan los de la FICHA del docente en el
          departamento de la sesion, como el plantel."""

        def read(m: Motor):
            perfil = ficha_salarial(m, cuil)
            antiguedad_anios, nivel = perfil["antiguedad_anios"], perfil["nivel_posgrado_salarial"]
            mes_obj = m.mes_ref_desde_periodo(periodo)
            mes_esc, df, total = m.construir_tabla_sueldo_docente(
                cuil, int(periodo["id"]), antiguedad_anios, nivel, mes_obj,
                fuente=m.designaciones_sueldo_resumen(cuil, int(periodo["id"])))
            return mes_obj, mes_esc, df, total, antiguedad_anios, nivel
        mes_obj, mes_esc, df, total, antiguedad_anios, nivel = self._read(scope, read)
        perfil = {"antiguedad_anios": antiguedad_anios, "nivel_posgrado_salarial": nivel}
        if not mes_esc:
            return {"estado": "sin_escala", "mes_objetivo": mes_obj, "perfil": perfil,
                    "mensaje": "No hay una escala salarial cargada para este período o para un mes anterior."}
        if df.empty:
            return {"estado": "sin_designaciones", "mes_objetivo": mes_obj, "mes_escala": mes_esc, "perfil": perfil,
                    "mensaje": "No hay designaciones para calcular sueldo en este período."}
        caption = (f"Escala utilizada: **{SR.etiqueta_mes_v256(mes_esc)}** · "
                   f"Antigüedad aplicada: **{SR.antiguedad_entera_v256(antiguedad_anios)} años "
                   f"({SR.porcentaje_antiguedad_v256(antiguedad_anios)*100:.0f}%)** · "
                   f"Posgrado: **{nivel or 'Sin adicional'} ({SR.porcentaje_posgrado_v256(nivel)*100:.0f}%)**. "
                   "Los porcentajes se calculan sobre el básico correspondiente a la dedicación; las designaciones "
                   "Ad Honorem computan $0.")
        mostrar = df.copy()
        for col in ["Básico simple", "Básico dedicación", "Adic. antigüedad", "Adic. posgrado", "Sueldo estimado"]:
            if col in mostrar.columns:
                mostrar[col] = mostrar[col].map(SR.moneda_v256)
        return {"estado": "ok", "mes_objetivo": mes_obj, "mes_escala": mes_esc, "caption": caption, "perfil": perfil,
                "filas": records(df), "filas_formateadas": records(mostrar), "total": total,
                "total_formateado": SR.moneda_v256(total)}

    def costos_asignaciones(self, scope: Scope, asignaciones: pd.DataFrame, periodo_contexto: Optional[dict]) -> dict:
        """Motor v257/v258 (``calcular_costos_asignaciones_proyecto_v257``) sobre asignaciones ya filtradas.

        Contrato: ``asignaciones`` con columnas ``id, proyecto_id, cuil, horas_asignadas, departamento_asignacion_id,
        fecha_inicio, fecha_fin`` (las de ``get_investigacion_docente`` / ``get_extension_docente`` rama
        ``todos_departamentos``) ya restringidas como ``act_v162`` (l. 33187-33201); ``periodo_contexto`` = periodo
        abierto de la pagina (``None`` -> sin costos)."""
        def read(m: Motor):
            return m.costos_asignaciones_v257(asignaciones, periodo_contexto)
        mes_esc, detalle, total = self._read(scope, read)
        return {"mes_escala": mes_esc, "detalle": detalle, "total": total,
                "por_proyecto": costos_por_proyecto(detalle)}

    def costos_proyectos_vigentes(self, scope: Scope, tipo: str) -> dict:
        """Costos de "📚 Proyectos vigentes" de Investigacion o Extension (l. 33173-33238) para el departamento de la
        sesion.  Lee con las lecturas YA PORTADAS de esos bloques (import, sin modificarlos) y aplica el motor v257.
        No se muestra en ningun modulo hasta la Etapa 4 (H3)."""
        if scope.department_id is None:
            raise SueldosError(409, "SCOPE_INSTITUTIONAL", MSG_INSTITUTIONAL)
        if tipo == "investigacion":
            from investigacion.lecturas import Lecturas
            from investigacion.repository import InvestigacionRepository as Repo
            from investigacion.service import InvestigacionService as Svc
        elif tipo == "extension":
            from extension.lecturas import Lecturas
            from extension.repository import ExtensionRepository as Repo
            from extension.service import ExtensionService as Svc
        else:
            raise SueldosError(422, "INVALID", MSG_VALOR_INVALIDO)
        try:
            with self._transaction() as conn:
                conn.execute("SET TRANSACTION READ ONLY")
                L = Lecturas(Repo(conn, scope.institution_id, scope.department_id), self.today(), scope.rol)
                abierto = L.periodo_abierto()
                asig = L.asignaciones(incluir_bajas=True, todos_departamentos=True)
                act = Svc._activas_del_periodo(L, asig if asig is not None else pd.DataFrame(), abierto)
                m = Motor(SueldosRepository(conn, scope.institution_id, scope.department_id), self.today())
                if abierto is not None and isinstance(act, pd.DataFrame) and not act.empty:
                    mes_esc, detalle, total = m.costos_asignaciones_v257(act, abierto)
                else:
                    mes_esc, detalle, total = None, pd.DataFrame(), 0.0
        except SueldosError:
            raise
        except Exception as exc:
            log.error("sueldos: costos de proyectos fallidos: %s", type(exc).__name__)
            raise SueldosError(503, "DB_READ", MSG_DB_READ) from None
        return {"periodo": _period(abierto), "mes_escala": mes_esc, "detalle": detalle, "total": total,
                "por_proyecto": costos_por_proyecto(detalle)}


__all__ = ["SueldosService", "SueldosError", "Scope", "SPEC_GUARDAR_ESCALA"]
