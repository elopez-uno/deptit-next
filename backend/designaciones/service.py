"""Reglas de pantalla de Designaciones (B13-FIX02) sobre la sesion y el contexto de ``auth``.

Alcance (decision humana, docs/designaciones_analysis.md §18): las 5 pestañas certificadas (entry l. 63392-64858):
listado del periodo con vista historica, foto al cierre, grilla de fechas con baja v207 e historial; alta; modificar /
finalizar (8 tipos); editar / eliminar por error; carga rapida con su modelo Excel.  Acto administrativo: elegir del
repositorio o dejar pendiente, vincular / desvincular (simple y masivo).  "Cargar un nuevo acto ahora" (E4-07): el
acto lo crea y lo compensa el owner documental (Resoluciones y respaldos) a traves del puerto ``ActoNuevo`` que
inyecta la composicion (``integraciones/acto_contextual.py``, D-E4-01); sin puerto, la opcion se rechaza como antes.
Alta desde la pagina Docentes (E4-08): contratos ``contexto_desde_docentes`` / ``alta_desde_docentes`` que usa
``integraciones/registro_designacion.py``, con los mismos writers y COMMITs del alta.
Carga rapida integral de Docentes (E4-09): ``guardar_fila_integral`` / ``movimiento_alta_integral``
(``integraciones/carga_integral.py``), los mismos writers por fila.
Efectos sobre Comisiones: solo la sincronizacion de cargo y la baja automatica de asignaciones v214, como el
certificado.

Cada writer certificado que la UI invoca es una operacion B12H propia (``correlation_id`` por writer):
1. comprobaciones de la pantalla sobre lecturas frescas: sin evento;
2. B10 del writer (``designaciones.write`` / ``designaciones.delete`` / ``movimientos.write`` /
   ``documentos.write`` / ``documentos.delete``): DENIED;
3. B12I capa U: SOLO en el primer writer del clic (el registro de lecturas se vacia al validarlo, como el
   certificado) se relee fresco lo que el usuario vio (``huella``); si cambio -> FAILED ``StaleDecisionError``;
4. cada COMMIT certificado con su SUCCESS (``commit_seq``) en esa transaccion; sin COMMITs -> SUCCESS
   POST_OPERATION; error -> FAILED con ``coupled_commits`` (lo ya confirmado queda, como el certificado).
El ambito (institucion/departamento) sale SIEMPRE de la sesion revalidada; ningun id de tenant llega del cliente.
Las lecturas nunca ejecutan reconciliaciones con escritura (B12F las omite fuera de una operacion de negocio).
"""

from __future__ import annotations

import hashlib
import json
import logging
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from typing import Any, Callable, Optional, Protocol

import pandas as pd
from psycopg import Connection

import audit
from auth import policy
from auth.service import AuthService, SessionRecord
from periodos.service import MSG_AUDIT_POST, MSG_DB_READ, MSG_DB_TRANSACTION, MSG_INSTITUTIONAL, MSG_STALE
from periodos.service import denial_message, scope_message

from . import escrituras as E
from . import excel, historial, rules
from .repository import DesignacionesRepository

log = logging.getLogger("deptit_next.designaciones")

DEP = policy.SCOPE_DEPARTMENT
ACTION_READ = policy.Action("designaciones", policy.OP_READ, DEP)
ACTION_WRITE = policy.Action("designaciones", policy.OP_WRITE, DEP)
ACTION_DELETE = policy.Action("designaciones", policy.OP_DELETE, DEP)
ACTION_MOVEMENT = policy.Action("movimientos", policy.OP_WRITE, DEP)
ACTION_DOC_WRITE = policy.Action("documentos", policy.OP_WRITE, DEP)
ACTION_DOC_DELETE = policy.Action("documentos", policy.OP_DELETE, DEP)


@dataclass(frozen=True)
class WriterSpec:
    """Writer del registro B10 (legacy_write_actions.py) y su etiqueta B12H (``entity_type_for``/``_entity_param``)."""
    action: policy.Action
    entity_type: str
    entity_param: Optional[str]


SPECS = {
    E.W_GUARDAR: WriterSpec(ACTION_WRITE, "designacion", "cuil"),
    E.W_ACTUALIZAR: WriterSpec(ACTION_WRITE, "designacion", None),
    E.W_POR_ERROR: WriterSpec(ACTION_WRITE, "designacion", None),
    E.W_FINALIZAR: WriterSpec(ACTION_WRITE, "designacion", None),
    E.W_FECHAS: WriterSpec(ACTION_WRITE, "designacion", None),
    E.W_ELIMINAR: WriterSpec(ACTION_DELETE, "designacion", None),
    E.W_ELIMINAR_MASIVO: WriterSpec(ACTION_DELETE, "designacion", None),
    E.W_MOVIMIENTO: WriterSpec(ACTION_MOVEMENT, "movimiento", "cuil"),
    E.W_BAJA_V207: WriterSpec(ACTION_MOVEMENT, "designacion", None),
    E.W_VINCULAR_DES: WriterSpec(ACTION_DOC_WRITE, "acto_administrativo", "designacion_id"),
    E.W_VINCULAR_MOV: WriterSpec(ACTION_DOC_WRITE, "acto_administrativo", "movimiento_id"),
    E.W_VINCULAR_DES_MASIVO: WriterSpec(ACTION_DOC_WRITE, "acto_administrativo", "documento_id"),
    E.W_DESVINCULAR_DES_MASIVO: WriterSpec(ACTION_DOC_DELETE, "acto_administrativo", None),
    E.W_VINCULAR_MOV_MASIVO: WriterSpec(ACTION_DOC_WRITE, "acto_administrativo", "documento_id"),
    E.W_DESVINCULAR_MOV_MASIVO: WriterSpec(ACTION_DOC_DELETE, "acto_administrativo", None),
    E.W_ESTADO_CONSULTA: WriterSpec(ACTION_WRITE, "designacion", "cuil"),
}

# --- textos certificados (entry l. 63392-64858; v266/v267 l. 54672-54760) ------------------------------------
MSG_SIN_PERIODO = "No hay período abierto. Creá uno en el módulo Períodos para cargar o modificar designaciones."
MSG_SIN_PERIODOS = "Todavía no hay períodos registrados."
MSG_ALTA_SIN_PERIODO = "Primero tenés que crear un período abierto."
MSG_ALTA_SIN_DOCENTES = "Primero tenés que registrar docentes."
MSG_NO_PERIODO_ABIERTO = "No hay período abierto."
MSG_FUNCION_ALTA = "Completá las funciones no docentes antes de guardar la designación."
MSG_FUNCION_MOD = "Completá las funciones no docentes antes de guardar la modificación."
MSG_FUNCION_CORR = "Completá las funciones no docentes antes de guardar la corrección."
MSG_DUPLICADA = ("La designación exactamente igual ya existe. Marcá la confirmación si corresponde a otro acto "
                 "administrativo u otra alta intencional.")
MSG_ALTA_OK = "Designación registrada correctamente."
# Pagina Docentes (E4-08, entry l. 60111-60118, 60323-60327, 60376-60380).
MSG_DUPLICADA_PERIODO = "La designación exactamente igual ya existe en el período actual."
MSG_FECHAS_INVERTIDAS = "La fecha hasta no puede ser anterior a la fecha desde."
PREFIX_ALTA = "No se pudo registrar la designación: "
MSG_MOD_OK = "Designación actualizada correctamente."
PREFIX_MOD = "No se pudo registrar la modificación: "
MSG_CORR_CONFIRMAR = "Tenés que confirmar que es una corrección de error."
MSG_ELIMINAR_CONFIRMAR = "Primero confirmá la eliminación por error."
PREFIX_MASIVO = "No se pudo completar la eliminación masiva: "
MSG_ACTO_SIN_SELECCION = ("Elegiste vincular un acto existente, pero todavía no seleccionaste ninguno. Seleccionalo o "
                          "elegí ‘Dejar pendiente’.")
MSG_CARGA_DOCENTES_FALTAN = "No se cargó nada. Primero registrá los docentes que faltan."
MSG_CARGA_DUPLICADOS = "No se cargó nada. Hay duplicados o errores: marcá la confirmación si realmente querés avanzar."
MSG_CARGA_SIN_FILAS = "No pude detectar filas válidas. Revisá que la tabla tenga CUIL y datos de designación."
# Textos propios de la API (no existen en Streamlit: alli la seleccion sale siempre de la tabla en pantalla) y la
# opcion de acto nuevo por la ruta JSON (sin PDF): rechazo defensivo.  Desde E4-07 el acto nuevo se carga con
# "Cargar un nuevo acto ahora" (multipart con el PDF); el texto anterior ("pendiente de migración") quedo desactualizado
# y se corrigio en la Etapa 5 / Tanda C (C6).
MSG_ACTO_NUEVO_PENDIENTE = ("Para cargar un nuevo acto administrativo usá la opción \"Cargar un nuevo acto ahora\" "
                            "del formulario, que adjunta el PDF. Elegí un acto del repositorio o dejá la operación "
                            "pendiente de vincular.")
MSG_ACTO_NO_ENCONTRADO = "El acto administrativo seleccionado ya no figura en el repositorio. Actualizá la pantalla."
# E4-07: sufijos certificados del mensaje de exito cuando el acto se creo en el mismo intento (l. 63787, 64146, 64291).
SUFIJO_ALTA_ACTO_NUEVO = " El nuevo acto también fue guardado en Resoluciones y respaldos."
# 6A-B3: registrar designacion desde Docentes con acto, cuando ya existia una designacion identica (no se crea otra).
MSG_ACTO_DESIGNACION_EXISTENTE = ("Ya existía una designación idéntica para este docente en el período: no se creó otra "
                                  "y su acto administrativo no se modificó.")
SUFIJO_BAJA_ACTO_NUEVO = " El nuevo acto administrativo fue guardado en Resoluciones y respaldos."
SUFIJO_MOD_ACTO_NUEVO = (" El nuevo acto administrativo fue guardado en Resoluciones y respaldos y quedó vinculado a la "
                         "modificación.")
MSG_DESIGNACION_NO_ENCONTRADA = "No se encontró la designación seleccionada. Actualizá la pantalla."
MSG_DOCENTE_NO_ENCONTRADO = "No se encontró el docente seleccionado. Actualizá la pantalla."
MSG_PERIODO_NO_ENCONTRADO = "No se encontró el período seleccionado."
MSG_VALOR_INVALIDO = "Uno de los valores enviados no es válido para este formulario."
MSG_PERIODO_NO_ENCONTRADO_CONSULTA = "El período seleccionado no existe en el departamento."
MSG_DOCENTE_NO_ENCONTRADO_CONSULTA = "El docente seleccionado no figura en el departamento."
MSG_SELECCION_INVALIDA = "La selección no corresponde a las filas mostradas. Actualizá la pantalla."
MSG_NO_HISTORICO = "La corrección de fechas con baja sincronizada solo aplica a un período histórico."

ROW_FIELDS = ("id", "periodo_id", "periodo", "nombre_completo", "cuil", "cargo", "dedicacion", "horas",
              "tipo_designacion", "numero_resolucion", "ad_honorem", "fecha_desde", "fecha_hasta",
              "fecha_hasta_prevista", "fecha_finalizacion_efectiva", "fecha_registro_finalizacion",
              "motivo_finalizacion", "estado", "observaciones", "funcion_no_docente", "texto_funcion_no_docente",
              "numero_resolucion_legacy", "acto_documento_id", "acto_administrativo", "acto_dependencia", "acto_fecha")


# Tabla "Designaciones del período" (entry l. 63415-63442): get_designaciones sin columnas técnicas.
DISPLAY_COLUMNS = ["periodo", "nombre_completo", "cuil", "cargo", "dedicacion", "horas", "tipo_designacion",
                   "ad_honorem", "fecha_desde", "fecha_hasta", "fecha_hasta_prevista", "fecha_finalizacion_efectiva",
                   "fecha_registro_finalizacion", "motivo_finalizacion", "estado", "observaciones", "Función",
                   "Funciones no docentes", "Acto administrativo"]


class DesignacionesError(Exception):
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


class ActoNuevo(Protocol):
    """Puerto E4-07 "Cargar un nuevo acto ahora" (D-E4-01): lo implementa la composicion con los writers del owner
    documental, ya ligado a la sesion, a los datos del formulario en linea y al PDF.  Designaciones no importa
    Resoluciones y respaldos (evita el ciclo con ``resoluciones_respaldos.escrituras``)."""

    def crear(self, categoria: str, periodo_id: int, referencia_texto: str, titulo_sugerido: str,
              detalle_sugerido: str, observaciones_sugeridas: str) -> int:
        """``_resolver_acto_contextual_v267`` modo "nuevo": crea el acto (sus COMMITs) y devuelve su id, o levanta
        ``DesignacionesError`` sin escribir."""

    def compensar(self, documento_id: int) -> None:
        """``_eliminar_acto_recien_creado_v267``: borra el acto recien creado; nunca levanta (como el certificado)."""


def _named(row: dict) -> dict:
    return {"id": int(row["id"]), "nombre": row.get("nombre")}


def _period(row: Optional[dict]) -> Optional[dict]:
    if row is None:
        return None
    return {k: _jsonable(row.get(k)) for k in ("id", "nombre", "anio", "semestre", "fecha_inicio", "fecha_fin",
                                                "estado")}


def _jsonable(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
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
    return {k: _jsonable(v) for k, v in row.items()}


def _hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def _fecha(value: Any) -> date:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        raise DesignacionesError(422, "INVALID", MSG_VALOR_INVALIDO) from None


def _opcion(value: Any, opciones: list) -> str:
    if not isinstance(value, str) or value not in opciones:
        raise DesignacionesError(422, "INVALID", MSG_VALOR_INVALIDO)
    return value


def _id(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise DesignacionesError(422, "INVALID", MSG_VALOR_INVALIDO)
    return value


def _ids(values: Any) -> list[int]:
    if not isinstance(values, list):
        raise DesignacionesError(422, "INVALID", MSG_VALOR_INVALIDO)
    return [_id(v) for v in values]


class DesignacionesService:
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
            raise DesignacionesError(409, "SCOPE_NOT_VERIFIED", scope_message(resolution))
        if not any(m[0] == "designaciones" for m in visible) or resolution.department is None:
            raise DesignacionesError(409, "SCOPE_INSTITUTIONAL", MSG_INSTITUTIONAL)
        return Scope(int(resolution.institution["id"]), int(resolution.department["id"]),
                     resolution.institution, resolution.department)

    def _require_read(self, record: SessionRecord) -> policy.ActorContext:
        actor = policy.actor_from_session(record.user, record.scope)
        decision = policy.decide(actor, ACTION_READ)
        if not decision.allowed:
            raise DesignacionesError(403, "DENIED", denial_message(decision, ACTION_READ))
        return actor

    def _read(self, scope: Scope, fn: Callable[[DesignacionesRepository], Any]) -> Any:
        try:
            with self._transaction() as conn:
                conn.execute("SET TRANSACTION READ ONLY")
                return fn(DesignacionesRepository(conn, scope.institution_id, scope.department_id))
        except DesignacionesError:
            raise
        except Exception as exc:
            log.error("designaciones: lectura fallida: %s", type(exc).__name__)
            raise DesignacionesError(503, "DB_READ", MSG_DB_READ) from None

    # ------------------------------------------------------------------ lecturas certificadas
    @staticmethod
    def _designaciones(repo: DesignacionesRepository, periodo_id: int) -> list[dict]:
        """``get_designaciones`` efectiva (v95 + v162 + v266 acto) con la huella de cada fila."""
        filas = repo.designaciones(int(periodo_id))
        actos = {int(a["designacion_id"]): a for a in repo.actos_designaciones([int(f["id"]) for f in filas])}
        out = []
        for f in filas:
            row = dict(f)
            row["funcion_no_docente"] = int(pd.to_numeric(row.get("funcion_no_docente"), errors="coerce") or 0)
            row["texto_funcion_no_docente"] = "" if row.get("texto_funcion_no_docente") is None \
                else str(row["texto_funcion_no_docente"])
            legacy = str(row.get("numero_resolucion") or "")
            row["numero_resolucion_legacy"] = legacy
            row["acto_documento_id"] = None
            row["acto_administrativo"] = ""
            row["acto_dependencia"] = ""
            row["acto_fecha"] = ""
            act = actos.get(int(row["id"]))
            if act:
                row["acto_documento_id"] = int(act.get("documento_id"))
                row["acto_administrativo"] = rules.etiqueta_acto(act.get("tipo_documento"), act.get("numero"),
                                                                 act.get("dependencia_emisora"))
                row["acto_dependencia"] = str(act.get("dependencia_emisora") or "")
                row["acto_fecha"] = str(act.get("fecha") or "")
            elif legacy.strip():
                row["acto_administrativo"] = f"Resolución {legacy.strip()} — pendiente de vincular al repositorio"
            else:
                row["acto_administrativo"] = "Pendiente de vincular"
            row = {k: _jsonable(row.get(k)) for k in ROW_FIELDS}
            row["huella"] = _hash(row)
            out.append(row)
        return out

    @staticmethod
    def _frame(rows: list[dict]) -> pd.DataFrame:
        return pd.DataFrame(rows, columns=list(ROW_FIELDS) + ["huella"]) if rows else pd.DataFrame(
            columns=list(ROW_FIELDS) + ["huella"])

    def _contexto(self, repo: DesignacionesRepository) -> dict:
        abierto, ultimo = repo.open_period(), repo.last_period()
        hist_abierto = False
        if abierto is not None:
            hist_abierto = rules.es_periodo_historico(repo.period_info(int(abierto["id"])), ultimo, abierto)
        return {"abierto": abierto, "ultimo": ultimo, "historico_abierto": hist_abierto}

    @staticmethod
    def _huella_periodo(period: Optional[dict]) -> Optional[str]:
        return None if period is None else _hash(_period(period))

    def overview(self, record: SessionRecord) -> dict:
        scope = self.scope(record)
        actor = self._require_read(record)

        def read(repo: DesignacionesRepository) -> dict:
            ctx = self._contexto(repo)
            docentes = [_clean({k: d.get(k) for k in ("cuil", "nombre_completo", "legajo", "titulo", "tipo_docente",
                                                       "estado")}) for d in repo.docentes()]
            return {**ctx, "periodos": repo.periods(), "docentes": docentes}

        data = self._read(scope, read)
        decide = lambda action: policy.decide(actor, action).allowed  # noqa: E731
        return {
            "contexto": {"institucion": _named(scope.institution), "departamento": _named(scope.department)},
            "abierto": _period(data["abierto"]),
            "abierto_huella": self._huella_periodo(data["abierto"]),
            "actual": _period(data["ultimo"]),
            "historico_abierto": data["historico_abierto"],
            "periodos": [_period(p) for p in data["periodos"]],
            "docentes": data["docentes"],
            "catalogos": {"cargos": rules.CARGOS, "dedicaciones": rules.DEDICACIONES,
                          "horas_por_dedicacion": rules.HORAS_POR_DEDICACION, "tipos": rules.TIPOS_DESIGNACION,
                          "estados": rules.ESTADOS_DESIGNACION, "ad_honorem": rules.AD_HONOREM,
                          "tipos_cambio": rules.TIPOS_CAMBIO,
                          "movimientos_con_acto": sorted(rules.MOVIMIENTOS_ACTO_ADMINISTRATIVO_V266)},
            "permisos": {"puede_escribir": decide(ACTION_WRITE), "puede_borrar": decide(ACTION_DELETE),
                         "puede_movimiento": decide(ACTION_MOVEMENT), "puede_vincular": decide(ACTION_DOC_WRITE),
                         "puede_desvincular": decide(ACTION_DOC_DELETE),
                         "es_superadmin": policy.normalize_role(record.user.get("rol")) == policy.ROLE_SUPERADMIN},
        }

    def _periodo_data(self, repo: DesignacionesRepository, periodo_id: int) -> dict:
        info = repo.period_info(int(periodo_id))
        if info is None:
            raise DesignacionesError(404, "NOT_FOUND", MSG_PERIODO_NO_ENCONTRADO)
        ctx = self._contexto(repo)
        historico = rules.es_periodo_historico(info, ctx["ultimo"], ctx["abierto"])
        filas = self._designaciones(repo, int(periodo_id))
        foto = rules.filtrar_foto_v183(self._frame(filas), historico, info)
        ids_foto = set(pd.to_numeric(foto.get("id", pd.Series(dtype=float)), errors="coerce").dropna().astype(int)
                       .tolist()) if not foto.empty else set()
        for f in filas:
            if historico:
                f["estado_mostrado"] = "Vigente al cierre" if int(f["id"]) in ids_foto \
                    else rules.estado_visible(f.get("estado"))
            else:
                f["estado_mostrado"] = rules.estado_visible(f.get("estado"))
            f["funcion"] = "No docente" if rules.es_funcion_no_docente(f.get("funcion_no_docente")) else "Docencia"
        if historico:
            conteo = len(foto)
        else:
            conteo = sum(1 for f in filas if f.get("estado") == "Activa")
        cache: dict[int, pd.DataFrame] = {}

        def designaciones_df(pid: int) -> pd.DataFrame:
            if int(pid) not in cache:
                cache[int(pid)] = self._frame(self._designaciones(repo, int(pid)))
            return cache[int(pid)]

        cache[int(periodo_id)] = self._frame([{k: f.get(k) for k in list(ROW_FIELDS) + ["huella"]} for f in filas])
        movs = historial.movimientos_designaciones_periodo(repo, int(periodo_id), designaciones_df)
        base, indicadores = historial.clasificar_v267(movs)
        hist_rows = []
        if not base.empty:
            for _, r in base.iterrows():
                hist_rows.append(_clean({
                    "id": r.get("id"), "fecha": r.get("fecha"), "cuil": r.get("cuil"), "nombre": r.get("nombre"),
                    "tipo_movimiento": r.get("tipo_movimiento"), "detalle": r.get("detalle"),
                    "acto_documento_id": r.get("acto_documento_id"),
                    "acto_administrativo": r.get("acto_administrativo"), "observaciones": r.get("observaciones"),
                    "variacion_horas": float(pd.to_numeric(r.get("variacion_horas_v267"), errors="coerce") or 0),
                    "categoria": r.get("categoria_movimiento_v267"),
                }))
                hist_rows[-1]["huella"] = _hash(hist_rows[-1])
        return {"periodo": _period(info), "historico": historico, "designaciones": filas, "conteo": int(conteo),
                "foto_ids": sorted(ids_foto), "historial": hist_rows, "indicadores": indicadores,
                "abierto": _period(ctx["abierto"])}

    def periodo(self, record: SessionRecord, periodo_id: Any) -> dict:
        scope = self.scope(record)
        self._require_read(record)
        pid = _id(periodo_id)
        return self._read(scope, lambda repo: self._periodo_data(repo, pid))

    def periodo_excel(self, record: SessionRecord, periodo_id: Any) -> tuple[bytes, str]:
        """``mostrar_boton_descarga_excel_tabla`` de la tabla histórica (hoja "Datos", columnas visibles)."""
        scope = self.scope(record)
        self._require_read(record)
        pid = _id(periodo_id)
        data = self._read(scope, lambda repo: self._periodo_data(repo, pid))
        if not data["historico"]:
            raise DesignacionesError(409, "NO_HISTORICO", MSG_NO_HISTORICO)
        df = pd.DataFrame([{**{c: f.get(c) for c in DISPLAY_COLUMNS[:14]}, "estado": f["estado_mostrado"],
                            "observaciones": f.get("observaciones"), "Función": f["funcion"],
                            "Funciones no docentes": f.get("texto_funcion_no_docente"),
                            "Acto administrativo": f.get("acto_administrativo")} for f in data["designaciones"]],
                          columns=DISPLAY_COLUMNS)
        out = BytesIO()
        try:
            with pd.ExcelWriter(out, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="Datos")
        except Exception:
            out = BytesIO()
            with pd.ExcelWriter(out, engine="openpyxl") as writer:
                df.astype(str).to_excel(writer, index=False, sheet_name="Datos")
        return out.getvalue(), f"Designaciones_{self.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

    def actos(self, record: SessionRecord) -> dict:
        """Repositorio de Resoluciones y respaldos para el selector v266 (solo lectura)."""
        scope = self.scope(record)
        self._require_read(record)
        docs = self._read(scope, lambda repo: repo.documentos())
        out = []
        for d in docs:
            row = _clean({k: d.get(k) for k in ("id", "fecha", "tipo_documento", "numero", "dependencia_emisora",
                                                 "categoria", "titulo", "detalle", "periodo")})
            row["etiqueta"] = rules.etiqueta_acto(d.get("tipo_documento"), d.get("numero"), d.get("dependencia_emisora"))
            out.append(row)
        return {"documentos": out}

    def modelo_excel(self, record: SessionRecord) -> bytes:
        scope = self.scope(record)
        self._require_read(record)

        def read(repo: DesignacionesRepository) -> dict:
            return {"docentes": repo.docentes(), "periodos": repo.periods(), "abierto": repo.open_period()}

        data = self._read(scope, read)
        return excel.generar_excel_modelo_carga_rapida_designaciones(
            data["docentes"], data["periodos"], periodo_default=data["abierto"], filas_modelo=5000)

    # ------------------------------------------------------------------ B10 + B12H por writer
    def _separate(self, op: audit.Operation, outcome: str, *, error_code: Optional[str] = None,
                  metadata: Optional[dict] = None) -> bool:
        mode = audit.MODE_POST_OPERATION if outcome == audit.OUTCOME_SUCCESS else audit.MODE_SEPARATE
        try:
            self.audit_store.append_separate(op.event(outcome, mode, error_code=error_code, metadata=metadata))
            return True
        except Exception as exc:
            log.error("B12H: el evento %s de %s no pudo persistirse (%s)", outcome, op.name, audit.error_code_of(exc))
            return False

    def _usuario(self, record: SessionRecord) -> str:
        """``_usuario_acto_v266``: email o nombre del usuario actual."""
        return str(record.user.get("email") or record.user.get("nombre") or "").strip()

    def _op(self, record: SessionRecord, scope: Scope, writer: str, fn: Callable[[E.Unidad], Any], *,
            entity_raw: Any = None, stale: Optional[Callable[[], None]] = None) -> tuple[Any, list[str]]:
        """Un writer certificado completo: B10 -> B12I (``stale``) -> sus COMMITs con SUCCESS, o FAILED."""
        spec = SPECS[writer]
        actor = policy.actor_from_session(record.user, record.scope)
        audit_actor = audit.actor_from_record(record.user, record.scope, record.meta)
        op = audit.Operation(writer, spec.action, spec.entity_type, audit_actor, spec.entity_param, entity_raw)
        decision = policy.decide(actor, spec.action)
        if not decision.allowed:
            self._separate(op, audit.OUTCOME_DENIED, error_code=decision.code,
                           metadata={"b10_decision": decision.code})
            raise DesignacionesError(403, "DENIED", denial_message(decision, spec.action), "PermissionError")
        unidad = E.Unidad(self._transaction, op, scope.institution_id, scope.department_id, today=self.today(),
                          now=self.now(), usuario=self._usuario(record))
        try:
            if stale is not None:
                stale()
            result = fn(unidad)
        except DesignacionesError as exc:
            self._separate(op, audit.OUTCOME_FAILED, error_code=exc.error_class,
                           metadata={"coupled_commits": op.coupled_commits})
            raise
        except ValueError as exc:
            self._separate(op, audit.OUTCOME_FAILED, error_code="ValueError",
                           metadata={"coupled_commits": op.coupled_commits})
            raise DesignacionesError(422, "REJECTED", str(exc)) from None
        except E.AuditoriaFallida:
            self._separate(op, audit.OUTCOME_FAILED, error_code="AuditPersistenceError:AUDIT_INSERT_FAILED",
                           metadata={"coupled_commits": op.coupled_commits})
            raise DesignacionesError(503, "AUDIT", f"{audit.MSG_PERSIST} [AUDIT_INSERT_FAILED]",
                                     "AuditPersistenceError") from None
        except Exception as exc:
            log.error("designaciones: %s falló tras %d COMMIT(s): %s", writer, op.coupled_commits, type(exc).__name__)
            self._separate(op, audit.OUTCOME_FAILED, error_code=audit.error_code_of(exc),
                           metadata={"coupled_commits": op.coupled_commits})
            raise DesignacionesError(503, "DB_ERROR", MSG_DB_TRANSACTION) from None
        if op.coupled_commits == 0:
            if not self._separate(op, audit.OUTCOME_SUCCESS,
                                  metadata={"coupled_commits": 0, "post_reason": "NO_POOLED_COMMIT"}):
                raise DesignacionesError(503, "AUDIT", MSG_AUDIT_POST)
        return result, unidad.avisos

    def _stale_rows(self, scope: Scope, periodo_id: int, esperado: dict[int, Any],
                    extra: Optional[Callable[[DesignacionesRepository], Optional[str]]] = None) -> Callable[[], None]:
        """B12I capa U: las filas que el usuario vio (``huella``) se releen frescas antes del primer writer."""
        def check() -> None:
            try:
                fresh = self._read(scope, lambda repo: {
                    "filas": {int(f["id"]): f["huella"] for f in self._designaciones(repo, periodo_id)},
                    "extra": extra(repo) if extra else None})
            except DesignacionesError:
                raise DesignacionesError(503, "FRESH_READ", MSG_DB_READ, "FreshReadError") from None
            for did, huella in esperado.items():
                if fresh["filas"].get(int(did)) != huella:
                    raise DesignacionesError(409, "STALE", f"{MSG_STALE} [B12I: get_designaciones]",
                                             "StaleDecisionError")
            if fresh["extra"] is not None:
                raise DesignacionesError(409, "STALE", f"{MSG_STALE} [B12I: {fresh['extra']}]", "StaleDecisionError")
        return check

    def _acto_contextual(self, scope: Scope, config: Any, acto_nuevo: Optional[ActoNuevo], categoria: str,
                         periodo_id: int, referencia_texto: str, titulo_sugerido: str, detalle_sugerido: str,
                         observaciones_sugeridas: str) -> tuple[Optional[int], bool]:
        """``_resolver_acto_contextual_v267`` (l. 54714): ``(documento_id, creado_ahora)``.  Modo "nuevo" (E4-07): el
        acto lo crea el puerto en ese mismo punto del flujo (despues de las comprobaciones de pantalla y antes del
        primer writer de Designaciones), como el certificado."""
        config = config if isinstance(config, dict) else {"modo": "pendiente"}
        if str(config.get("modo") or "pendiente") == "nuevo" and acto_nuevo is not None:
            return int(acto_nuevo.crear(categoria, periodo_id, referencia_texto, titulo_sugerido, detalle_sugerido,
                                        observaciones_sugeridas)), True
        return self._acto(scope, config), False

    @staticmethod
    def _compensar(acto_nuevo: Optional[ActoNuevo], documento_id: Optional[int]) -> None:
        """``_eliminar_acto_recien_creado_v267`` (l. 54761) en los 3 puntos certificados; nunca oculta el error original."""
        if acto_nuevo is None or documento_id is None:
            return
        try:
            acto_nuevo.compensar(int(documento_id))
        except Exception as exc:  # el certificado ignora cualquier fallo de la compensacion
            log.error("designaciones: compensación del acto recién creado fallida: %s", type(exc).__name__)

    def _acto(self, scope: Scope, config: Any) -> Optional[int]:
        """``_resolver_acto_contextual_v267`` para los modos existente / pendiente.  "nuevo" sin puerto (ruta JSON, sin
        PDF ni datos del acto) se rechaza con el mensaje controlado anterior a E4-07."""
        config = config if isinstance(config, dict) else {"modo": "pendiente"}
        modo = str(config.get("modo") or "pendiente")
        if modo == "pendiente":
            return None
        if modo == "nuevo":
            raise DesignacionesError(409, "ACTO_NUEVO_PENDIENTE", MSG_ACTO_NUEVO_PENDIENTE)
        if modo != "existente":
            return None
        documento_id = config.get("documento_id")
        if not rules.id_documento_valido(documento_id):
            raise DesignacionesError(422, "ACTO_SIN_SELECCION", MSG_ACTO_SIN_SELECCION)
        if isinstance(documento_id, bool) or not isinstance(documento_id, int):
            raise DesignacionesError(422, "INVALID", MSG_VALOR_INVALIDO)
        ids = self._read(scope, lambda repo: {int(d["id"]) for d in repo.documentos()})
        if documento_id not in ids:
            raise DesignacionesError(409, "ACTO_NO_ENCONTRADO", MSG_ACTO_NO_ENCONTRADO)
        return int(documento_id)

    @staticmethod
    def _duplicada(repo: DesignacionesRepository, periodo_id, cuil, cargo, dedicacion, horas, tipo, ad_honorem,
                   fecha_desde, fecha_hasta, estado=None, numero_resolucion=None, funcion_no_docente=None) -> bool:
        """``existe_designacion_duplicada`` (l. 7838)."""
        horas = rules.horas_segun_dedicacion(dedicacion, horas)
        resolucion = None if numero_resolucion is None else str(numero_resolucion or "").strip()
        filas = repo.match(periodo_id, str(cuil).strip(), str(cargo).strip(), str(dedicacion).strip(),
                           int(horas) if not rules._is_na(horas) else 0, str(tipo).strip(), str(ad_honorem).strip(),
                           str(fecha_desde), str(fecha_hasta), estado=estado, estado_on=estado is not None,
                           resolucion=resolucion,
                           funcion=None if funcion_no_docente is None else (1 if funcion_no_docente else 0))
        return bool(filas)

    # ------------------------------------------------------------------ Pestaña 2: nueva designación
    def _alta_valores(self, data: dict, abierto: dict) -> dict:
        cargo = _opcion(data.get("cargo"), rules.CARGOS)
        dedicacion = _opcion(data.get("dedicacion"), rules.DEDICACIONES)
        tipo = _opcion(data.get("tipo_designacion"), rules.TIPOS_DESIGNACION)
        ad_honorem = _opcion(data.get("ad_honorem"), rules.AD_HONOREM)
        estado = _opcion(data.get("estado"), rules.ESTADOS_DESIGNACION)
        desde = _fecha(data.get("fecha_desde")) if data.get("fecha_desde") not in (None, "") else \
            rules.safe_date(abierto.get("fecha_inicio"), self.today())
        hasta = _fecha(data.get("fecha_hasta")) if data.get("fecha_hasta") not in (None, "") else \
            rules.safe_date(abierto.get("fecha_fin"), self.today())
        funcion = data.get("funcion_no_docente") is True
        return {"cargo": cargo, "dedicacion": dedicacion, "horas": rules.horas_segun_dedicacion(dedicacion),
                "tipo": tipo, "ad_honorem": ad_honorem, "estado": estado, "desde": desde, "hasta": hasta,
                "funcion": funcion, "texto": _text(data.get("texto_funcion_no_docente")) if funcion else "",
                "observaciones": _text(data.get("observaciones"))}

    def duplicado(self, record: SessionRecord, data: dict) -> dict:
        scope = self.scope(record)
        self._require_read(record)

        def read(repo: DesignacionesRepository) -> dict:
            abierto = repo.open_period()
            if abierto is None:
                return {"duplicada": False}
            v = self._alta_valores(data, abierto)
            return {"duplicada": self._duplicada(repo, int(abierto["id"]), _text(data.get("cuil")).strip(), v["cargo"],
                                                 v["dedicacion"], v["horas"], v["tipo"], v["ad_honorem"], v["desde"],
                                                 v["hasta"], v["estado"], numero_resolucion=None,
                                                 funcion_no_docente=v["funcion"])}

        return self._read(scope, read)

    def alta(self, record: SessionRecord, data: dict, acto_nuevo: Optional[ActoNuevo] = None) -> dict:
        scope = self.scope(record)

        def screen(repo: DesignacionesRepository) -> dict:
            return {"abierto": repo.open_period(), "docentes": repo.docentes()}

        s = self._read(scope, screen)
        abierto = s["abierto"]
        if abierto is None:
            raise DesignacionesError(409, "NO_OPEN_PERIOD", MSG_ALTA_SIN_PERIODO, tone="warning")
        if not s["docentes"]:
            raise DesignacionesError(409, "NO_DOCENTES", MSG_ALTA_SIN_DOCENTES, tone="warning")
        cuil_sel = _text(data.get("cuil"))
        fila = next((d for d in s["docentes"] if str(d.get("cuil") or "") == cuil_sel), None)
        if fila is None:
            raise DesignacionesError(404, "NOT_FOUND", MSG_DOCENTE_NO_ENCONTRADO)
        cuil = str(fila.get("cuil") or "").strip()
        nombre = str(fila.get("nombre_completo") or "").strip()
        v = self._alta_valores(data, abierto)
        pid, per_nombre = int(abierto["id"]), abierto["nombre"]
        dup = self._read(scope, lambda repo: self._duplicada(
            repo, pid, cuil, v["cargo"], v["dedicacion"], v["horas"], v["tipo"], v["ad_honorem"], v["desde"],
            v["hasta"], v["estado"], numero_resolucion=None, funcion_no_docente=v["funcion"]))
        confirmar = data.get("confirmar_duplicada") is True and dup
        if v["funcion"] and not rules.texto_funcion_limpio(v["texto"]):
            raise DesignacionesError(422, "FUNCION_REQUERIDA", MSG_FUNCION_ALTA)
        if dup and not confirmar:
            raise DesignacionesError(409, "DUPLICADA", MSG_DUPLICADA)
        func_label = "No docente" if v["funcion"] else "Docencia"
        detalle_acto = (f"{per_nombre} - {nombre} - {cargo_txt(v)} - {v['dedicacion']} - {v['horas']} hs - {v['tipo']} - "
                        f"Función: {func_label}")  # _detalle_acto_alta_v267 (l. 63709)
        try:
            acto, creado = self._acto_contextual(
                scope, data.get("acto"), acto_nuevo, "Designación docente", pid,
                f"Designación: {nombre} — CUIL {cuil}", f"Designación — {nombre}", detalle_acto, v["observaciones"])
        except DesignacionesError as exc:
            raise DesignacionesError(exc.status, exc.code, exc.message, exc.error_class) from None
        huella_abierto = data.get("abierto_huella")

        def stale_extra(repo: DesignacionesRepository) -> Optional[str]:
            return None if self._huella_periodo(repo.open_period()) == huella_abierto else "get_periodo_abierto"

        stale = self._stale_rows(scope, pid, {}, stale_extra)
        detalle = (f"{per_nombre} - {cargo_txt(v)} - {v['dedicacion']} - {v['horas']} hs - {v['tipo']} - "
                   f"Función: {func_label}")
        if v["funcion"]:
            detalle += f" - Tareas: {rules.texto_funcion_limpio(v['texto'])}"
        avisos: list[str] = []
        did = None
        try:
            did, av = self._op(record, scope, E.W_GUARDAR, lambda u: E.guardar_designacion(
                u, pid, cuil, v["cargo"], v["dedicacion"], v["horas"], v["tipo"], v["ad_honorem"], v["desde"],
                v["hasta"], v["estado"], v["observaciones"], permitir_duplicada=confirmar, numero_resolucion="",
                funcion_no_docente=v["funcion"], texto_funcion_no_docente=v["texto"]), entity_raw=cuil, stale=stale)
            avisos += av
            if acto is not None and did is not None:
                self._op(record, scope, E.W_VINCULAR_DES, lambda u: E.vincular_acto_designacion(u, did, acto),
                         entity_raw=did)
            mov_id, _ = self._op(record, scope, E.W_MOVIMIENTO, lambda u: E.registrar_movimiento(
                u, "Alta de designación", cuil, nombre, detalle, v["observaciones"], pid,
                horas_variacion=0 if v["funcion"] else v["horas"]), entity_raw=cuil)
            if acto is not None and mov_id is not None:
                self._op(record, scope, E.W_VINCULAR_MOV, lambda u: E.vincular_acto_movimiento(u, mov_id, acto),
                         entity_raw=mov_id)
        except DesignacionesError as exc:
            # l. 63794: si ni siquiera llego a existir la designacion, no queda un acto recien creado huerfano.
            if did is None and creado:
                self._compensar(acto_nuevo, acto)
            raise DesignacionesError(exc.status, exc.code, PREFIX_ALTA + exc.message, exc.error_class) from None
        return {"mensaje": MSG_ALTA_OK + (SUFIJO_ALTA_ACTO_NUEVO if creado else ""), "tono": "success",
                "avisos": avisos, "id": did}

    # ------------------------------------------------------------------ E4-08 / E4-09: alta desde Docentes
    def contexto_desde_docentes(self, record: SessionRecord) -> dict:
        """Lo que la pagina Docentes necesita de Designaciones para registrar una designacion (E4-08): periodo abierto
        (``get_periodo_abierto``), su huella B12I, los catalogos del formulario y los CUIL con alguna designacion en
        ese periodo (``get_designaciones(periodo_abierto)``, v266 efectiva).  Lectura sin B10 propio: la pagina es
        Docentes y la composicion exige ``docentes.read`` (``DocentesService.overview``)."""
        scope = self.scope(record)

        def read(repo: DesignacionesRepository) -> dict:
            abierto = repo.open_period()
            cuiles = set()
            if abierto is not None:
                cuiles = {str(d.get("cuil") or "").strip() for d in self._designaciones(repo, int(abierto["id"]))}
            return {"abierto": abierto, "cuiles": cuiles}

        data = self._read(scope, read)
        return {"abierto": _period(data["abierto"]), "abierto_huella": self._huella_periodo(data["abierto"]),
                "cuiles_periodo": data["cuiles"],
                "catalogos": {"cargos": rules.CARGOS, "dedicaciones": rules.DEDICACIONES,
                              "horas_por_dedicacion": rules.HORAS_POR_DEDICACION, "tipos": rules.TIPOS_DESIGNACION,
                              "estados": rules.ESTADOS_DESIGNACION, "ad_honorem": rules.AD_HONOREM}}

    def alta_desde_docentes(self, record: SessionRecord, data: dict, *, cuil: str, nombre: str,
                            detalle_movimiento: Optional[Callable[[dict, dict], str]], verificar_duplicada: bool,
                            msg_sin_periodo: str, stale: Optional[Callable[[], None]] = None,
                            antes_de_escribir: Optional[Callable[[Callable[[], None]], bool]] = None,
                            acto: Any = None, acto_nuevo: Optional[ActoNuevo] = None) -> dict:
        """Designacion registrada desde la pagina Docentes (entry l. 60086-60122, 60309-60356, 60365-60392).

        Mismos writers y limites de COMMIT que el alta de Designaciones (D-E4-06): ``guardar_designacion`` y, si el
        camino lo registra, ``registrar_movimiento("Alta de designación", ...)`` con el detalle propio del camino.
        Comprobaciones de la pantalla certificada, en su orden: duplicado exacto (solo reincorporacion), fecha hasta
        anterior a fecha desde y funciones no docentes.  ``cuil`` / ``nombre`` los resuelve la composicion desde
        Docentes (nunca el cliente).  ``antes_de_escribir(stale)`` corre despues de las comprobaciones y antes del
        primer writer de Designaciones (alta local del docente compartido, owner Docentes); devuelve si escribio y,
        en ese caso, ya consumio la verificacion B12I del primer writer del clic.

        6A-B3 (aceptacion): ``acto`` opcional con la misma semantica que el alta de Designaciones (existente /
        nuevo con ``acto_nuevo`` / pendiente; ``None`` = sin acto, comportamiento certificado intacto).  Se resuelve en
        el mismo punto que el alta (despues de las comprobaciones, antes del primer writer) y se vincula con
        ``vincular_acto_designacion_v266`` a la designacion y, si el camino registra movimiento, con
        ``vincular_acto_movimiento_v266`` al movimiento de alta.  Si la designacion no llega a existir, el acto
        recien creado se compensa (``_eliminar_acto_recien_creado_v267``), como en el alta."""
        scope = self.scope(record)
        abierto = self._read(scope, lambda repo: repo.open_period())
        if abierto is None:
            raise DesignacionesError(409, "NO_OPEN_PERIOD", msg_sin_periodo)
        v = self._alta_valores(data, abierto)
        pid = int(abierto["id"])
        if verificar_duplicada and self._read(scope, lambda repo: self._duplicada(
                repo, pid, cuil, v["cargo"], v["dedicacion"], v["horas"], v["tipo"], v["ad_honorem"], v["desde"],
                v["hasta"], v["estado"], numero_resolucion=None, funcion_no_docente=v["funcion"])):
            raise DesignacionesError(409, "DUPLICADA", MSG_DUPLICADA_PERIODO)
        if v["hasta"] < v["desde"]:
            raise DesignacionesError(422, "FECHAS", MSG_FECHAS_INVERTIDAS)
        if v["funcion"] and not rules.texto_funcion_limpio(v["texto"]):
            raise DesignacionesError(422, "FUNCION_REQUERIDA", MSG_FUNCION_ALTA)
        huella_abierto = data.get("abierto_huella")
        base = self._stale_rows(scope, pid, {}, lambda repo: None if self._huella_periodo(repo.open_period())
                                == huella_abierto else "get_periodo_abierto")

        def verificar() -> None:
            base()
            if stale is not None:
                stale()

        documento_id, creado = None, False
        if acto is not None:
            func_label = "No docente" if v["funcion"] else "Docencia"
            detalle_acto = (f"{abierto['nombre']} - {nombre} - {cargo_txt(v)} - {v['dedicacion']} - {v['horas']} hs - "
                            f"{v['tipo']} - Función: {func_label}")  # _detalle_acto_alta_v267, como el alta
            documento_id, creado = self._acto_contextual(
                scope, acto, acto_nuevo, "Designación docente", pid, f"Designación: {nombre} — CUIL {cuil}",
                f"Designación — {nombre}", detalle_acto, v["observaciones"])
        previas: set = set()
        if documento_id is not None:  # guardar_designacion devuelve el id de una identica ya existente sin crearla
            previas = self._read(scope, lambda repo: {int(d["id"]) for d in self._designaciones(repo, pid)
                                                      if str(d.get("cuil") or "").strip() == cuil})
        did = None
        try:
            if antes_de_escribir is not None and antes_de_escribir(verificar):
                verificar_designacion = None
            else:
                verificar_designacion = verificar
            did, avisos = self._op(record, scope, E.W_GUARDAR, lambda u: E.guardar_designacion(
                u, pid, cuil, v["cargo"], v["dedicacion"], v["horas"], v["tipo"], v["ad_honorem"], v["desde"],
                v["hasta"], v["estado"], v["observaciones"], funcion_no_docente=v["funcion"],
                texto_funcion_no_docente=v["texto"]), entity_raw=cuil, stale=verificar_designacion)
            if documento_id is not None and did is not None and int(did) in previas:
                # No se creo una designacion: no se reemplaza el acto de la existente (R1) y no queda acto huerfano.
                if creado:
                    self._compensar(acto_nuevo, documento_id)
                documento_id, creado = None, False
                avisos = list(avisos or []) + [MSG_ACTO_DESIGNACION_EXISTENTE]
            if documento_id is not None and did is not None:
                self._op(record, scope, E.W_VINCULAR_DES,
                         lambda u: E.vincular_acto_designacion(u, did, documento_id), entity_raw=did)
            mov_id = None
            if detalle_movimiento is not None:
                mov_id, _ = self._op(record, scope, E.W_MOVIMIENTO, lambda u: E.registrar_movimiento(
                    u, "Alta de designación", cuil, nombre, detalle_movimiento(abierto, v), v["observaciones"], pid,
                    horas_variacion=0 if v["funcion"] else v["horas"]), entity_raw=cuil)
            if documento_id is not None and mov_id is not None:
                self._op(record, scope, E.W_VINCULAR_MOV,
                         lambda u: E.vincular_acto_movimiento(u, mov_id, documento_id), entity_raw=mov_id)
        except Exception:
            if did is None and creado:  # l. 63794: sin designacion no queda un acto recien creado huerfano
                self._compensar(acto_nuevo, documento_id)
            raise
        return {"id": did, "avisos": avisos, "periodo": _period(abierto), "acto_documento_id": documento_id,
                "acto_creado": creado}

    def guardar_fila_integral(self, record: SessionRecord, fila: dict) -> Any:
        """``_guardar_fila_designacion_integral_v220`` (l. 49830) para la carga integral de Docentes (E4-09): una fila ya
        revisada por ``analizar_carga_integral_docentes_designaciones`` (servidor; periodo detectado por fechas dentro
        del departamento de la sesion) -> ``guardar_designacion(..., permitir_duplicada=False, numero_resolucion)``,
        sus COMMITs y su B10/B12H."""
        scope = self.scope(record)
        cuil = str(fila["cuil"])
        did, _ = self._op(record, scope, E.W_GUARDAR, lambda u: E.guardar_designacion(
            u, int(fila["periodo_id"]), cuil, fila["cargo"], fila["dedicacion"], int(fila["horas"]),
            fila["tipo_designacion"], fila["ad_honorem"], fila["fecha_desde"], fila["fecha_hasta"], fila["estado"],
            fila["observaciones"], permitir_duplicada=False, numero_resolucion=fila["numero_resolucion"]),
            entity_raw=cuil)
        return did

    def movimiento_alta_integral(self, record: SessionRecord, *, cuil: str, nombre: str, detalle: str,
                                 observaciones: Any, periodo_id: int, horas: int) -> None:
        """Movimiento "Alta de designación" de una fila verificada en la base (carga integral, l. 61540-61552)."""
        scope = self.scope(record)
        self._op(record, scope, E.W_MOVIMIENTO, lambda u: E.registrar_movimiento(
            u, "Alta de designación", cuil, nombre, detalle, observaciones, periodo_id, horas_variacion=horas),
            entity_raw=cuil)

    # ------------------------------------------------------------------ Pestaña 3: modificar / finalizar
    def _abierto_y_fila(self, scope: Scope, designacion_id: int, excluir_finalizadas: bool) -> dict:
        def read(repo: DesignacionesRepository) -> dict:
            abierto = repo.open_period()
            if abierto is None:
                return {"abierto": None}
            filas = self._designaciones(repo, int(abierto["id"]))
            if excluir_finalizadas:
                filas = [f for f in filas if str(f.get("estado") or "").strip().lower() != "finalizada"]
            return {"abierto": abierto, "fila": next((f for f in filas if int(f["id"]) == designacion_id), None)}

        s = self._read(scope, read)
        if s["abierto"] is None:
            raise DesignacionesError(409, "NO_OPEN_PERIOD", MSG_NO_PERIODO_ABIERTO, tone="warning")
        if s["fila"] is None:
            raise DesignacionesError(404, "NOT_FOUND", MSG_DESIGNACION_NO_ENCONTRADA)
        return s

    def modificar(self, record: SessionRecord, data: dict, acto_nuevo: Optional[ActoNuevo] = None) -> dict:
        scope = self.scope(record)
        did = _id(data.get("id"))
        tipo_cambio = _opcion(data.get("tipo_cambio"), rules.TIPOS_CAMBIO)
        s = self._abierto_y_fila(scope, did, excluir_finalizadas=True)
        abierto, fila = s["abierto"], s["fila"]
        pid, per_nombre = int(abierto["id"]), abierto["nombre"]
        hoy = self.today()

        nuevo_cargo = fila["cargo"]
        nueva_dedicacion = fila["dedicacion"]
        nuevas_horas = int(fila["horas"]) if fila.get("horas") is not None else 10
        nuevo_tipo = fila["tipo_designacion"]
        nuevo_adh = fila["ad_honorem"] or "No"
        nueva_funcion = rules.es_funcion_no_docente(fila.get("funcion_no_docente"))
        nuevo_texto = rules.texto_funcion_limpio(fila.get("texto_funcion_no_docente", ""))
        texto_anterior = nuevo_texto
        nuevo_estado = fila["estado"] or "Activa"
        nueva_desde = rules.safe_date(fila["fecha_desde"], rules.safe_date(abierto["fecha_inicio"], hoy))
        nueva_hasta = rules.safe_date(fila["fecha_hasta"], rules.safe_date(abierto["fecha_fin"], hoy))
        fecha_baja = None
        motivo_baja = ""

        if tipo_cambio == "Cambio de cargo":
            nuevo_cargo = _opcion(data.get("cargo"), rules.CARGOS)
        elif tipo_cambio in ("Aumento de dedicación", "Disminución de dedicación"):
            nueva_dedicacion = _opcion(data.get("dedicacion"), rules.DEDICACIONES)
            nuevas_horas = rules.horas_segun_dedicacion(nueva_dedicacion, fila.get("horas", 0))
        elif tipo_cambio == "Cambio de tipo de designación":
            nuevo_tipo = _opcion(data.get("tipo_designacion"), rules.TIPOS_DESIGNACION)
        elif tipo_cambio == "Cambio de condición Ad Honorem":
            nuevo_adh = _opcion(data.get("ad_honorem"), rules.AD_HONOREM)
        elif tipo_cambio == "Cambio de función docente / no docente":
            nueva_funcion = data.get("funcion_no_docente") is True
        elif tipo_cambio == rules.TIPO_BAJA:
            nuevo_estado = "Finalizada"
            fecha_baja = _fecha(data.get("fecha_baja"))
            motivo_baja = _text(data.get("motivo_baja"))
        elif tipo_cambio == rules.TIPO_GENERAL:
            nuevo_cargo = _opcion(data.get("cargo"), rules.CARGOS)
            nueva_dedicacion = _opcion(data.get("dedicacion"), rules.DEDICACIONES)
            nuevas_horas = rules.horas_segun_dedicacion(nueva_dedicacion, fila.get("horas", 0))
            nuevo_tipo = _opcion(data.get("tipo_designacion"), rules.TIPOS_DESIGNACION)
            nuevo_adh = _opcion(data.get("ad_honorem"), rules.AD_HONOREM)
            nueva_desde = _fecha(data.get("fecha_desde"))
            nueva_hasta = _fecha(data.get("fecha_hasta"))
            nuevo_estado = _opcion(data.get("estado"), rules.ESTADOS_DESIGNACION)
            nueva_funcion = data.get("funcion_no_docente") is True
        if nueva_funcion and tipo_cambio != rules.TIPO_BAJA:
            nuevo_texto = _text(data.get("texto_funcion_no_docente"))
        elif not nueva_funcion:
            nuevo_texto = ""
        nuevas_obs = _text(data.get("observaciones"))
        acto_config = data.get("acto") if tipo_cambio in rules.MOVIMIENTOS_ACTO_ADMINISTRATIVO_V266 else None
        stale = self._stale_rows(scope, pid, {did: data.get("huella")})
        detalle_anterior = "Antes: " + rules.detalle_designacion(fila)
        horas_actuales = int(fila["horas"]) if fila.get("horas") is not None else 0
        nombre, cuil = fila["nombre_completo"], fila["cuil"]

        if tipo_cambio == rules.TIPO_BAJA:
            prevista_txt = str(fila.get("fecha_hasta_prevista") or fila.get("fecha_hasta") or "")
            detalle_baja = (f"{per_nombre} - {detalle_anterior}. Fecha efectiva de baja: {fecha_baja}. "
                            f"Vencimiento previsto conservado: {prevista_txt}. ID designación original: {did}.")
            acto, creado = self._acto_contextual(
                scope, acto_config, acto_nuevo, rules.categoria_respaldo_movimiento("Baja de designación"), pid,
                f"Baja de designación: {nombre} — CUIL {cuil}", f"Baja de designación — {nombre}", detalle_baja,
                motivo_baja)
            mov_id = None
            try:
                res, _ = self._op(record, scope, E.W_FINALIZAR, lambda u: E.finalizar_designacion_anticipadamente(
                    u, did, fecha_baja, motivo_baja), stale=stale)
                no_docente = rules.es_funcion_no_docente(fila.get("funcion_no_docente"))
                mov_id, _ = self._op(record, scope, E.W_MOVIMIENTO, lambda u: E.registrar_movimiento(
                    u, "Baja de designación", cuil, nombre, detalle_baja, motivo_baja, pid,
                    horas_variacion=0 if no_docente else -horas_actuales, fecha_movimiento=fecha_baja),
                    entity_raw=cuil)
                if acto is not None and mov_id is not None:
                    self._op(record, scope, E.W_VINCULAR_MOV, lambda u: E.vincular_acto_movimiento(u, mov_id, acto),
                             entity_raw=mov_id)
            except DesignacionesError:
                if creado and mov_id is None:  # l. 64155
                    self._compensar(acto_nuevo, acto)
                raise
            n_com = int((res or {}).get("_comisiones_finalizadas_auto", 0) or 0)
            mensaje = ("Designación finalizada. Se conservaron por separado el vencimiento previsto, la fecha efectiva "
                       "de baja y la fecha de registro.")
            if creado:
                mensaje += SUFIJO_BAJA_ACTO_NUEVO
            if n_com:
                mensaje += (f" Además, al quedar sin otra designación docente vigente, se dieron de baja "
                            f"automáticamente {n_com} asignación/es activa/s a comisión del período con la misma "
                            "fecha efectiva.")
            return {"mensaje": mensaje, "tono": "success"}

        horas_nuevas = int(nuevas_horas or 0)
        texto_nuevo = rules.texto_funcion_limpio(nuevo_texto)
        error = ""
        fila_funcion = rules.es_funcion_no_docente(fila.get("funcion_no_docente"))
        if nueva_funcion and not texto_nuevo:
            error = MSG_FUNCION_MOD
        elif tipo_cambio == "Aumento de dedicación":
            if horas_nuevas <= horas_actuales:
                error = (f"No se guardó el movimiento: un aumento de dedicación debe aumentar las horas "
                         f"({horas_actuales} hs → {horas_nuevas} hs).")
        elif tipo_cambio == "Disminución de dedicación":
            if horas_nuevas >= horas_actuales:
                error = (f"No se guardó el movimiento: una disminución de dedicación debe reducir las horas "
                         f"({horas_actuales} hs → {horas_nuevas} hs).")
        elif tipo_cambio == "Cambio de cargo" and str(nuevo_cargo or "").strip() == str(fila.get("cargo") or "").strip():
            error = "No se efectuó ninguna modificación: el cargo seleccionado es el mismo que el actual."
        elif tipo_cambio == "Cambio de tipo de designación" and \
                str(nuevo_tipo or "").strip() == str(fila.get("tipo_designacion") or "").strip():
            error = "No se efectuó ninguna modificación: el tipo de designación no cambió."
        elif tipo_cambio == "Cambio de condición Ad Honorem" and \
                str(nuevo_adh or "").strip() == str(fila.get("ad_honorem") or "No").strip():
            error = "No se efectuó ninguna modificación: la condición Ad Honorem no cambió."
        elif (tipo_cambio == "Cambio de función docente / no docente" and bool(nueva_funcion) == bool(fila_funcion)
              and texto_nuevo == texto_anterior):
            error = "No se efectuó ninguna modificación: la función y su descripción no cambiaron."
        elif tipo_cambio == rules.TIPO_GENERAL:
            cambios = [
                str(nuevo_cargo or "").strip() != str(fila.get("cargo") or "").strip(),
                str(nueva_dedicacion or "").strip() != str(fila.get("dedicacion") or "").strip(),
                horas_nuevas != horas_actuales,
                str(nuevo_tipo or "").strip() != str(fila.get("tipo_designacion") or "").strip(),
                str(nuevo_adh or "").strip() != str(fila.get("ad_honorem") or "No").strip(),
                bool(nueva_funcion) != bool(fila_funcion),
                texto_nuevo != texto_anterior,
                str(nueva_desde) != str(fila.get("fecha_desde") or ""),
                str(nueva_hasta) != str(fila.get("fecha_hasta") or ""),
                str(nuevo_estado or "").strip() != str(fila.get("estado") or "").strip(),
                str(nuevas_obs or "").strip() != str(fila.get("observaciones") or "").strip(),
            ]
            if not any(cambios):
                error = "No se efectuó ninguna modificación. No se guardó ningún movimiento."
        if error:
            return {"mensaje": error, "tono": "info", "sin_cambios": True}

        detalle_nuevo = (f"Ahora: {nuevo_cargo} - {nueva_dedicacion} - {nuevas_horas} hs - {nuevo_tipo} - "
                         f"Ad Honorem: {nuevo_adh} - Función: {'No docente' if nueva_funcion else 'Docencia'}"
                         + (f" - Tareas: {texto_nuevo}" if nueva_funcion else "") + f" - Estado {nuevo_estado}")
        tipo_mov = tipo_cambio
        if tipo_cambio == "Cambio de condición Ad Honorem":
            tipo_mov = "Pase a Ad Honorem" if rules.normalizar_clave(nuevo_adh) in {"SI", "SÍ"} else "Pase a Rentado"
        if (tipo_cambio == "Cambio de función docente / no docente" and bool(nueva_funcion) == bool(fila_funcion)
                and texto_nuevo != texto_anterior):
            tipo_mov = "Cambio de funciones no docentes"
        antes = 0 if fila_funcion else horas_actuales
        despues = 0 if nueva_funcion else int(nuevas_horas or 0)
        if tipo_mov in ("Aumento de dedicación", "Disminución de dedicación", "Cambio de cargo", "Modificación general",
                        "Cambio de función docente / no docente"):
            variacion = despues - antes
        else:
            variacion = 0
        detalle_mov = f"{per_nombre} - {detalle_anterior} / {detalle_nuevo}"
        acto, creado = None, False
        if tipo_mov in rules.MOVIMIENTOS_ACTO_ADMINISTRATIVO_V266:
            acto, creado = self._acto_contextual(
                scope, acto_config, acto_nuevo, rules.categoria_respaldo_movimiento(tipo_mov), pid,
                f"{tipo_mov}: {nombre} — CUIL {cuil}", f"{tipo_mov} — {nombre}", detalle_mov, nuevas_obs)
        mov_id = None
        try:
            self._op(record, scope, E.W_ACTUALIZAR, lambda u: E.actualizar_designacion(
                u, did, nuevo_cargo, nueva_dedicacion, nuevas_horas, nuevo_tipo, nuevo_adh, nueva_desde, nueva_hasta,
                nuevo_estado, nuevas_obs, numero_resolucion=None, funcion_no_docente=nueva_funcion,
                texto_funcion_no_docente=texto_nuevo), stale=stale)
            mov_id, _ = self._op(record, scope, E.W_MOVIMIENTO, lambda u: E.registrar_movimiento(
                u, tipo_mov, cuil, nombre, detalle_mov, nuevas_obs, pid, horas_variacion=variacion), entity_raw=cuil)
            if acto is not None and mov_id is not None:
                self._op(record, scope, E.W_VINCULAR_MOV, lambda u: E.vincular_acto_movimiento(u, mov_id, acto),
                         entity_raw=mov_id)
        except DesignacionesError as exc:
            if creado and mov_id is None:  # l. 64296
                self._compensar(acto_nuevo, acto)
            raise DesignacionesError(exc.status, exc.code, PREFIX_MOD + exc.message, exc.error_class) from None
        return {"mensaje": MSG_MOD_OK + (SUFIJO_MOD_ACTO_NUEVO if creado else ""), "tono": "success"}

    # ------------------------------------------------------------------ Pestaña 4: editar / eliminar por error
    def corregir(self, record: SessionRecord, data: dict) -> dict:
        scope = self.scope(record)
        did = _id(data.get("id"))
        s = self._abierto_y_fila(scope, did, excluir_finalizadas=False)
        fila, pid = s["fila"], int(s["abierto"]["id"])
        cargo = _opcion(data.get("cargo"), rules.CARGOS)
        dedicacion = _opcion(data.get("dedicacion"), rules.DEDICACIONES)
        horas = rules.horas_segun_dedicacion(dedicacion, fila.get("horas", 0))
        tipo = _opcion(data.get("tipo_designacion"), rules.TIPOS_DESIGNACION)
        ad_honorem = _opcion(data.get("ad_honorem"), rules.AD_HONOREM)
        funcion = data.get("funcion_no_docente") is True
        desde, hasta = _fecha(data.get("fecha_desde")), _fecha(data.get("fecha_hasta"))
        estado = _opcion(data.get("estado"), rules.ESTADOS_DESIGNACION)
        texto = _text(data.get("texto_funcion_no_docente")) if funcion else ""
        obs = _text(data.get("observaciones"))
        if funcion and not rules.texto_funcion_limpio(texto):
            raise DesignacionesError(422, "FUNCION_REQUERIDA", MSG_FUNCION_CORR)
        if data.get("confirmar") is not True:
            raise DesignacionesError(422, "CONFIRMATION_REQUIRED", MSG_CORR_CONFIRMAR)
        stale = self._stale_rows(scope, pid, {did: data.get("huella")})
        n, _ = self._op(record, scope, E.W_POR_ERROR, lambda u: E.actualizar_designacion_por_error(
            u, did, cargo, dedicacion, horas, tipo, ad_honorem, desde, hasta, estado, obs, numero_resolucion=None,
            funcion_no_docente=funcion, texto_funcion_no_docente=texto), stale=stale)
        return {"mensaje": ("Designación corregida sin registrar movimiento. "
                            f"Se limpiaron {n} movimiento/s que describían datos ya inexistentes."), "tono": "success"}

    def guardar_estado_consulta(self, record: SessionRecord, data: dict) -> dict:
        """"💾 Guardar estado de la consulta" del Resumen docente (entry l. 61239-61249; E4-06).  Writer certificado
        ``guardar_estado_consulta_designacion`` (B10 ``designaciones.write``, B12H entidad ``designacion`` por ``cuil``).
        Hardening NEXT: el docente debe ser de la base maestra del departamento de la sesion, el periodo del
        departamento y el estado uno de los del selector (vacio = "⚪ Sin estado")."""
        scope = self.scope(record)
        cuil = data.get("cuil")
        periodo_id = data.get("periodo_id")
        estado = data.get("estado")
        if not isinstance(cuil, str) or not cuil.strip():
            raise DesignacionesError(422, "INVALID", MSG_VALOR_INVALIDO)
        if isinstance(periodo_id, bool) or not isinstance(periodo_id, int):
            raise DesignacionesError(422, "INVALID", MSG_VALOR_INVALIDO)
        if not isinstance(estado, str) or estado.strip() not in [""] + rules.ESTADOS_CONSULTA_DESIGNACION:
            raise DesignacionesError(422, "INVALID", MSG_VALOR_INVALIDO)
        cuil = cuil.strip()

        def read(repo: DesignacionesRepository) -> tuple:
            return repo.period_info(periodo_id), {str(d.get("cuil") or "") for d in repo.docentes()}
        periodo, cuiles = self._read(scope, read)
        if periodo is None:
            raise DesignacionesError(404, "NOT_FOUND", MSG_PERIODO_NO_ENCONTRADO_CONSULTA)
        if cuil not in cuiles:
            raise DesignacionesError(404, "NOT_FOUND", MSG_DOCENTE_NO_ENCONTRADO_CONSULTA)
        self._op(record, scope, E.W_ESTADO_CONSULTA,
                 lambda u: E.guardar_estado_consulta_designacion(u, cuil, periodo_id, estado.strip()), entity_raw=cuil)
        return {"mensaje": "Estado de la consulta guardado.", "tono": "success", "estado": estado.strip()}

    def eliminar(self, record: SessionRecord, data: dict) -> dict:
        scope = self.scope(record)
        did = _id(data.get("id"))
        s = self._abierto_y_fila(scope, did, excluir_finalizadas=False)
        if data.get("confirmar") is not True:
            raise DesignacionesError(422, "CONFIRMATION_REQUIRED", MSG_ELIMINAR_CONFIRMAR)
        stale = self._stale_rows(scope, int(s["abierto"]["id"]), {did: data.get("huella")})
        res, _ = self._op(record, scope, E.W_ELIMINAR, lambda u: E.eliminar_designacion(u, did), stale=stale)
        return {"mensaje": ("Designación eliminada sin registrar movimiento. "
                            f"También se eliminaron {res.get('movimientos_eliminados', 0)} movimiento/s que habían "
                            "quedado vinculados a esa carga errónea."), "tono": "warning"}

    def eliminar_masivo(self, record: SessionRecord, data: dict) -> dict:
        scope = self.scope(record)
        seleccion = data.get("seleccion")
        if not isinstance(seleccion, list) or not seleccion:
            raise DesignacionesError(422, "INVALID", MSG_VALOR_INVALIDO)
        esperado = {}
        for item in seleccion:
            if not isinstance(item, dict):
                raise DesignacionesError(422, "INVALID", MSG_VALOR_INVALIDO)
            esperado[_id(item.get("id"))] = item.get("huella")
        if data.get("confirmar") is not True:
            raise DesignacionesError(422, "CONFIRMATION_REQUIRED", MSG_ELIMINAR_CONFIRMAR)

        def read(repo: DesignacionesRepository) -> dict:
            abierto = repo.open_period()
            if abierto is None:
                return {"abierto": None}
            return {"abierto": abierto, "ids": {int(f["id"]) for f in self._designaciones(repo, int(abierto["id"]))}}

        s = self._read(scope, read)
        if s["abierto"] is None:
            raise DesignacionesError(409, "NO_OPEN_PERIOD", MSG_NO_PERIODO_ABIERTO, tone="warning")
        if not set(esperado) <= s["ids"]:
            raise DesignacionesError(409, "SELECCION", MSG_SELECCION_INVALIDA)
        stale = self._stale_rows(scope, int(s["abierto"]["id"]), esperado)
        try:
            res, _ = self._op(record, scope, E.W_ELIMINAR_MASIVO,
                              lambda u: E.eliminar_designaciones_masivo(u, sorted(esperado)), stale=stale)
        except DesignacionesError as exc:
            raise DesignacionesError(exc.status, exc.code, PREFIX_MASIVO + exc.message, exc.error_class) from None
        mensaje = (f"Se eliminaron {res.get('designaciones_eliminadas', 0)} designación/es por error de carga y "
                   f"{res.get('movimientos_eliminados', 0)} movimiento/s vinculado/s. ")
        if res.get("no_encontradas", 0):
            mensaje += f"No se encontraron {res.get('no_encontradas', 0)} fila/s al momento de ejecutar. "
        mensaje += "No se registró un nuevo movimiento por esta corrección."
        return {"mensaje": mensaje, "tono": "warning"}

    def _cambios_fechas(self, cambios: Any, filas: dict[int, dict], hasta_col: str, etiquetas: tuple[str, str, str],
                        ) -> tuple[list[tuple], list[str]]:
        """Filas con cambios reales en la grilla y errores de validación (entry l. 63513-63547 / 64451-64464)."""
        if not isinstance(cambios, list):
            raise DesignacionesError(422, "INVALID", MSG_VALOR_INVALIDO)
        validos, errores = [], []
        for item in cambios:
            if not isinstance(item, dict):
                raise DesignacionesError(422, "INVALID", MSG_VALOR_INVALIDO)
            did = _id(item.get("id"))
            fila = filas.get(did)
            if fila is None:
                raise DesignacionesError(409, "SELECCION", MSG_SELECCION_INVALIDA)
            desde = rules.fecha_iso_correccion_directa_v171(item.get("desde"))
            hasta = rules.fecha_iso_correccion_directa_v171(item.get("hasta"))
            original = (rules.fecha_iso_correccion_directa_v171(fila.get("fecha_desde")),
                        rules.fecha_iso_correccion_directa_v171(fila.get(hasta_col)))
            if (desde, hasta) == original:
                continue
            if not desde or not hasta:
                errores.append(f"Designación ID {did}: {etiquetas[0]}")
            elif desde > hasta:
                errores.append(f"Designación ID {did}: {etiquetas[1]}")
            else:
                validos.append((did, item.get("huella"), desde, hasta, original[1]))
        return validos, errores

    def fechas(self, record: SessionRecord, data: dict) -> dict:
        """Grilla Desde/Hasta de "Editar / eliminar por error" (sin movimientos)."""
        scope = self.scope(record)

        def read(repo: DesignacionesRepository) -> dict:
            abierto = repo.open_period()
            if abierto is None:
                return {"abierto": None}
            filas = self._designaciones(repo, int(abierto["id"]))
            for f in filas:
                prevista = str(f.get("fecha_hasta_prevista") or "").strip()
                f["_hasta_correccion_v171"] = f.get("fecha_hasta_prevista") if prevista else f.get("fecha_hasta")
            return {"abierto": abierto, "filas": {int(f["id"]): f for f in filas}}

        s = self._read(scope, read)
        if s["abierto"] is None:
            raise DesignacionesError(409, "NO_OPEN_PERIOD", MSG_NO_PERIODO_ABIERTO, tone="warning")
        validos, errores = self._cambios_fechas(data.get("cambios"), s["filas"], "_hasta_correccion_v171",
                                                ("Desde y Hasta son obligatorios.",
                                                 "Desde no puede ser posterior a Hasta.", ""))
        if errores:
            raise DesignacionesError(422, "FECHAS", "No se pueden guardar los cambios de fechas:\n- "
                                     + "\n- ".join(errores))
        if not validos:
            return {"mensaje": "No hay cambios directos pendientes.", "tono": "info", "sin_cambios": True}
        stale = self._stale_rows(scope, int(s["abierto"]["id"]), {v[0]: v[1] for v in validos})
        for pos, (did, _huella, desde, hasta, _orig) in enumerate(validos):
            legacy = str(s["filas"][did].get("numero_resolucion_legacy") or "").strip()
            self._op(record, scope, E.W_FECHAS, lambda u: E.actualizar_fechas_v171(u, did, legacy, desde, hasta),
                     stale=stale if pos == 0 else None)
        return {"mensaje": f"Se guardaron {len(validos)} corrección/es directas de fechas sin registrar movimientos.",
                "tono": "success"}

    def fechas_historicas(self, record: SessionRecord, data: dict) -> dict:
        """Grilla de fechas del período histórico (v203) con sincronización de baja v207."""
        scope = self.scope(record)
        pid = _id(data.get("periodo_id"))

        def read(repo: DesignacionesRepository) -> dict:
            info = repo.period_info(pid)
            if info is None:
                return {"info": None}
            ctx = self._contexto(repo)
            filas = self._designaciones(repo, pid)
            return {"info": info, "historico": rules.es_periodo_historico(info, ctx["ultimo"], ctx["abierto"]),
                    "filas": {int(f["id"]): f for f in filas}}

        s = self._read(scope, read)
        if s["info"] is None:
            raise DesignacionesError(404, "NOT_FOUND", MSG_PERIODO_NO_ENCONTRADO)
        if not s["historico"]:
            raise DesignacionesError(409, "NO_HISTORICO", MSG_NO_HISTORICO)
        validos, errores = self._cambios_fechas(data.get("cambios"), s["filas"], "fecha_hasta",
                                                ("fecha_desde y fecha_hasta son obligatorias.",
                                                 "fecha_desde no puede ser posterior a fecha_hasta.", ""))
        if errores:
            raise DesignacionesError(422, "FECHAS", "No se pueden guardar las correcciones de fechas:\n- "
                                     + "\n- ".join(errores))
        if not validos:
            return {"mensaje": "No hay cambios de fechas pendientes.", "tono": "info", "sin_cambios": True}
        stale = self._stale_rows(scope, pid, {v[0]: v[1] for v in validos})
        bajas = 0
        avisos: list[str] = []
        for pos, (did, _huella, desde, hasta, hasta_anterior) in enumerate(validos):
            resolucion = str(s["filas"][did].get("numero_resolucion") or "").strip()
            self._op(record, scope, E.W_FECHAS, lambda u: E.actualizar_fechas_v171(u, did, resolucion, desde, hasta),
                     stale=stale if pos == 0 else None)
            if str(hasta or "") != str(hasta_anterior or ""):
                try:
                    res, _ = self._op(record, scope, E.W_BAJA_V207, lambda u: E.sincronizar_baja_v207(
                        u, did, hasta, origen="corrección de fecha_hasta en grilla histórica"))
                    bajas += int((res or {}).get("cambios", 0) or 0)
                except DesignacionesError as exc:
                    avisos.append(f"Las fechas de la designación ID {did} se guardaron, pero no se pudo sincronizar su "
                                  f"movimiento de baja: {exc.message}")
        return {"mensaje": (f"Se guardaron {len(validos)} corrección/es de fechas del período histórico. "
                            f"Movimientos de baja sincronizados: {bajas}."), "tono": "success", "avisos": avisos}

    # ------------------------------------------------------------------ Actos: vincular / desvincular (v267)
    def vincular(self, record: SessionRecord, data: dict, quitar: bool) -> dict:
        scope = self.scope(record)
        destino = data.get("destino")
        if destino not in ("designaciones", "movimientos"):
            raise DesignacionesError(422, "INVALID", MSG_VALOR_INVALIDO)
        pid = _id(data.get("periodo_id"))
        seleccion = data.get("seleccion")
        if not isinstance(seleccion, list) or not seleccion:
            raise DesignacionesError(422, "INVALID", MSG_VALOR_INVALIDO)
        esperado: dict[int, Any] = {}
        for item in seleccion:
            if not isinstance(item, dict):
                raise DesignacionesError(422, "INVALID", MSG_VALOR_INVALIDO)
            esperado[_id(item.get("id")) if destino == "designaciones" else _mov_id(item.get("id"))] = item.get("huella")

        def read(repo: DesignacionesRepository) -> dict:
            if repo.period_info(pid) is None:
                return {"ok": False}
            if destino == "designaciones":
                return {"ok": True, "ids": {int(f["id"]): f["huella"] for f in self._designaciones(repo, pid)}}
            data_p = self._periodo_data(repo, pid)
            return {"ok": True, "ids": {int(h["id"]): h["huella"] for h in data_p["historial"]
                                        if h.get("tipo_movimiento") in rules.MOVIMIENTOS_ACTO_ADMINISTRATIVO_V266}}

        s = self._read(scope, read)
        if not s["ok"]:
            raise DesignacionesError(404, "NOT_FOUND", MSG_PERIODO_NO_ENCONTRADO)
        if not set(esperado) <= set(s["ids"]):
            raise DesignacionesError(409, "SELECCION", MSG_SELECCION_INVALIDA)
        ids = sorted(esperado)

        def stale() -> None:
            fresh = self._read(scope, read)
            for i, h in esperado.items():
                if fresh.get("ids", {}).get(i) != h:
                    raise DesignacionesError(409, "STALE", f"{MSG_STALE} [B12I: get_designaciones]",
                                             "StaleDecisionError")

        if quitar:
            writer = E.W_DESVINCULAR_DES_MASIVO if destino == "designaciones" else E.W_DESVINCULAR_MOV_MASIVO
            n, _ = self._op(record, scope, writer, lambda u: E.desvincular_actos_masivo(u, writer, ids), stale=stale)
            if destino == "designaciones":
                return {"mensaje": f"Se quitaron {n} vínculo/s. Las designaciones quedaron pendientes de vincular.",
                        "tono": "warning"}
            return {"mensaje": f"Se quitaron {n} vínculo/s de movimiento.", "tono": "warning"}
        documento_id = self._acto(scope, {"modo": "existente", "documento_id": data.get("documento_id")})
        writer = E.W_VINCULAR_DES_MASIVO if destino == "designaciones" else E.W_VINCULAR_MOV_MASIVO
        n, _ = self._op(record, scope, writer, lambda u: E.vincular_actos_masivo(u, writer, ids, documento_id),
                        entity_raw=documento_id, stale=stale)
        etiqueta = "designación/es" if destino == "designaciones" else "movimiento/s"
        return {"mensaje": f"Acto administrativo vinculado a {n} {etiqueta}.", "tono": "success"}

    # ------------------------------------------------------------------ Pestaña 5: carga rápida
    def _parse(self, repo: DesignacionesRepository, texto: Any) -> pd.DataFrame:
        try:
            return rules.parsear_designaciones_pegadas(texto, pd.DataFrame(repo.periods()), self.today())
        except Exception as exc:
            log.info("designaciones: tabla pegada no interpretable: %s", type(exc).__name__)
            raise DesignacionesError(422, "PARSE", MSG_CARGA_SIN_FILAS) from None

    def _analisis_carga(self, repo: DesignacionesRepository, df: pd.DataFrame) -> dict:
        abierto = repo.open_period()
        inexistentes = []
        for idx, row in df.iterrows():
            cuil_row = rules.limpiar_cuil(row.get("cuil", ""))
            if repo.docente_existe(rules.clave_cuil(cuil_row)) is None:
                inexistentes.append({"fila_pegada": int(idx) + 1, "cuil": cuil_row,
                                     "motivo": "No existe en base maestra de docentes"})
        duplicadas, vistas = [], set()
        for idx, row in df.iterrows():
            horas_auto = rules.horas_segun_dedicacion(row.get("dedicacion", ""), row.get("horas", 0))
            nombre_p = rules.limpiar_texto_tabla(row.get("periodo", "")) or (abierto["nombre"] if abierto else "")
            periodo = repo.period_by_name(nombre_p) if nombre_p else abierto
            periodo_id = periodo["id"] if periodo else None
            clave = (periodo_id, rules.limpiar_cuil(row.get("cuil", "")), rules.normalizar_clave(row.get("cargo", "")),
                     rules.normalizar_clave(row.get("dedicacion", "")), int(horas_auto or 0),
                     rules.normalizar_clave(row.get("tipo_designacion", "")),
                     rules.normalizar_clave(row.get("numero_resolucion", "")),
                     rules.normalizar_clave(row.get("ad_honorem", "")),
                     rules.limpiar_texto_tabla(row.get("fecha_desde", "")),
                     rules.limpiar_texto_tabla(row.get("fecha_hasta", "")), rules.normalizar_clave(row.get("estado", "")))
            en_pegado = clave in vistas
            vistas.add(clave)
            existe = False
            if periodo_id is not None:
                existe = self._duplicada(repo, periodo_id, row.get("cuil", ""), row.get("cargo", ""),
                                         row.get("dedicacion", ""), horas_auto, row.get("tipo_designacion", ""),
                                         row.get("ad_honorem", ""), row.get("fecha_desde", ""),
                                         row.get("fecha_hasta", ""), row.get("estado", ""),
                                         numero_resolucion=row.get("numero_resolucion", ""))
            if en_pegado or existe or periodo is None:
                motivo = "Duplicada dentro de la tabla pegada" if en_pegado else "Ya existe en la base"
                if periodo is None:
                    motivo = "Período inexistente"
                duplicadas.append({"fila_pegada": int(idx) + 1, "periodo": nombre_p, "cuil": row.get("cuil", ""),
                                   "cargo": row.get("cargo", ""), "dedicacion": row.get("dedicacion", ""),
                                   "horas": horas_auto, "tipo_designacion": row.get("tipo_designacion", ""),
                                   "numero_resolucion": row.get("numero_resolucion", ""), "motivo": motivo})
        return {"abierto": abierto, "inexistentes": inexistentes, "duplicadas": duplicadas}

    def carga_preview(self, record: SessionRecord, texto: Any) -> dict:
        scope = self.scope(record)
        self._require_read(record)

        def read(repo: DesignacionesRepository) -> dict:
            df = self._parse(repo, texto)
            if df.empty:
                return {"filas": [], "inexistentes": [], "duplicados": [],
                        "aviso": MSG_CARGA_SIN_FILAS if str(texto or "").strip() else None}
            a = self._analisis_carga(repo, df)
            return {"filas": [_clean(r) for r in df.to_dict(orient="records")], "inexistentes": a["inexistentes"],
                    "duplicados": [_clean(d) for d in a["duplicadas"]], "aviso": None}

        return self._read(scope, read)

    def carga_ejecutar(self, record: SessionRecord, texto: Any, confirmar: Any) -> dict:
        scope = self.scope(record)

        def read(repo: DesignacionesRepository) -> dict:
            df = self._parse(repo, texto)
            return {"df": df, **(self._analisis_carga(repo, df) if not df.empty else {})}

        s = self._read(scope, read)
        df = s["df"]
        if df.empty:
            raise DesignacionesError(422, "PARSE", MSG_CARGA_SIN_FILAS)
        if s["inexistentes"]:
            raise DesignacionesError(422, "DOCENTES_FALTAN", MSG_CARGA_DOCENTES_FALTAN)
        hay_dup = bool(s["duplicadas"])
        if hay_dup and confirmar is not True:
            raise DesignacionesError(422, "DUPLICATES", MSG_CARGA_DUPLICADOS)
        confirmar_dup = hay_dup and confirmar is True
        abierto = s["abierto"]
        cargadas = omitidas = 0
        vistas: set = set()
        for pos, (_, row) in enumerate(df.iterrows(), start=1):
            try:
                nombre_p = rules.limpiar_texto_tabla(row.get("periodo", "")) or (abierto["nombre"] if abierto else "")
                periodo = self._read(scope, lambda repo: repo.period_by_name(nombre_p)) if nombre_p else abierto
                if periodo is None:
                    omitidas += 1
                    continue
                cuil_row = rules.limpiar_cuil(row.get("cuil", ""))
                cargo_row = rules.limpiar_texto_tabla(row.get("cargo", ""))
                dedicacion_row = rules.limpiar_texto_tabla(row.get("dedicacion", ""))
                horas_row = rules.horas_segun_dedicacion(dedicacion_row, row.get("horas", 0))
                tipo_row = rules.limpiar_texto_tabla(row.get("tipo_designacion", ""))
                resolucion_row = rules.limpiar_texto_tabla(row.get("numero_resolucion", ""))
                ad_row = rules.limpiar_texto_tabla(row.get("ad_honorem", "")) or "No"
                desde_row = rules.limpiar_texto_tabla(row.get("fecha_desde", ""))
                hasta_row = rules.limpiar_texto_tabla(row.get("fecha_hasta", ""))
                estado_row = rules.limpiar_texto_tabla(row.get("estado", "")) or "Activa"
                obs_row = rules.limpiar_texto_tabla(row.get("observaciones", ""))
                pid = int(periodo["id"])
                clave = (pid, cuil_row, rules.normalizar_clave(cargo_row), rules.normalizar_clave(dedicacion_row),
                         horas_row, rules.normalizar_clave(tipo_row), rules.normalizar_clave(resolucion_row),
                         rules.normalizar_clave(ad_row), desde_row, hasta_row, rules.normalizar_clave(estado_row))
                if clave in vistas and not confirmar_dup:
                    omitidas += 1
                    continue
                vistas.add(clave)
                duplicada = self._read(scope, lambda repo: self._duplicada(
                    repo, pid, cuil_row, cargo_row, dedicacion_row, horas_row, tipo_row, ad_row, desde_row, hasta_row,
                    estado_row, numero_resolucion=resolucion_row))
                if duplicada and not confirmar_dup:
                    omitidas += 1
                    continue
                self._op(record, scope, E.W_GUARDAR, lambda u: E.guardar_designacion(
                    u, pid, cuil_row, cargo_row, dedicacion_row, horas_row, tipo_row, ad_row, desde_row, hasta_row,
                    estado_row, obs_row, permitir_duplicada=confirmar_dup, numero_resolucion=resolucion_row),
                    entity_raw=cuil_row)
                doc = self._read(scope, lambda repo: repo.docente_existe(rules.clave_cuil(cuil_row)))
                if doc is not None:
                    from docentes.rules import nombre_completo
                    nombre_doc = nombre_completo(doc.get("apellido", ""), doc.get("nombres", "")) or doc.get("nombre", "")
                else:
                    nombre_doc = ""
                self._op(record, scope, E.W_MOVIMIENTO, lambda u: E.registrar_movimiento(
                    u, "Alta de designación", cuil_row, nombre_doc,
                    f"{periodo['nombre']} - {cargo_row} - {dedicacion_row} - {horas_row} hs - {tipo_row}", obs_row, pid,
                    horas_variacion=horas_row), entity_raw=cuil_row)
                cargadas += 1
            except DesignacionesError as exc:
                raise DesignacionesError(exc.status, exc.code, (
                    f"La carga se interrumpió en la fila {pos}: {exc.message} Filas ya procesadas antes del error: "
                    f"cargadas {cargadas}, omitidas {omitidas}."), exc.error_class) from None
        return {"mensaje": f"Carga finalizada. Designaciones cargadas: {cargadas}. Omitidas: {omitidas}.",
                "tono": "success"}


def cargo_txt(v: dict) -> str:
    return v["cargo"]


def _mov_id(value: Any) -> int:
    """Ids del historial: incluye los sinteticos negativos del primer periodo (v269), como la tabla certificada."""
    if isinstance(value, bool) or not isinstance(value, int) or value == 0:
        raise DesignacionesError(422, "INVALID", MSG_VALOR_INVALIDO)
    return value
