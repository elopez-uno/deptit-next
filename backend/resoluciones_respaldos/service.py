"""Reglas de pantalla de Resoluciones y respaldos (B13-FIX02, ``render_repositorio_documental_v249`` l. 51514-52129).

Alcance (decisiones D-AK1..D-AK14, docs/resoluciones_respaldos_analysis.md §36): las 3 pestañas certificadas
(📚 Repositorio, ➕ Cargar acto, 🏛️ Dependencias).  No existen (y no se agregan) edicion de numero/fecha/tipo, borrado
solo del PDF, borrado de dependencias, versionado, ZIP, Excel, importacion ni exportacion.  El PDF vive en
``documentos_respaldo.archivo_pdf`` (``bytea``): no hay filesystem ni rutas.

Cada writer certificado que la UI invoca es una operacion B12H propia (``correlation_id`` por writer):
1. comprobaciones de la pantalla (mismos mensajes que el certificado) y hardening NEXT aprobado (multipart, tope de
   50 MiB, firma ``%PDF-``): sin evento;
2. B10 del writer (``documentos.write`` departamento; dependencias ``documentos.write`` INSTITUCION; eliminar
   ``documentos.delete`` -> solo superadmin): DENIED en transaccion propia;
3. B12I: sin lock de capa T ni comparacion optimista (no hay familia documental; decision explicita del bloque);
4. sus COMMITs certificados con SUCCESS (``commit_seq``); errores -> FAILED con ``coupled_commits``.
El ambito sale SIEMPRE de la sesion revalidada; ningun id de tenant llega del cliente.  El listado y el detalle nunca
traen el binario (D-AK12): el PDF baja solo por la descarga, que re-consulta la fila con el ambito de la sesion.
Ninguna lectura escribe (D-AK7: sin DDL, siembras v262 ni migraciones v251/v261/v266).
"""

from __future__ import annotations

import logging
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable, Optional

import pandas as pd
import psycopg
from psycopg import Connection

import audit
from auth import policy
from auth.service import AuthService, SessionRecord
from comisiones.service import _jsonable
from periodos.service import MSG_AUDIT_POST, MSG_DB_READ, MSG_DB_TRANSACTION, MSG_INSTITUTIONAL
from periodos.service import denial_message, scope_message

from . import escrituras as E
from . import rules as R
from .lecturas import (Lecturas, opciones_dependencias_alta, opciones_dependencias_correccion, opciones_periodo_alta,
                       opciones_periodo_docentes)
from .repository import DocumentosRepository

log = logging.getLogger("deptit_next.resoluciones_respaldos")

MODULO = "resoluciones_respaldos"
DOMINIO = "documentos"
DEP = policy.SCOPE_DEPARTMENT
ACTION_READ = policy.Action(DOMINIO, policy.OP_READ, DEP)
ACTION_WRITE = policy.Action(DOMINIO, policy.OP_WRITE, DEP)
ACTION_DELETE = policy.Action(DOMINIO, policy.OP_DELETE, DEP)
ACTION_WRITE_INSTITUCION = policy.Action(DOMINIO, policy.OP_WRITE, policy.SCOPE_INSTITUTION)


@dataclass(frozen=True)
class WriterSpec:
    """Writer del registro B10 (``legacy_write_actions.py`` l. 195-215) y su etiqueta B12H
    (docs/audit/resoluciones_respaldos_phase_a/b10_b12h_resoluciones.txt)."""
    name: str
    action: policy.Action
    entity_type: str
    entity_param: Optional[str]


# D-AK13: el alta toma ``proyecto_id`` como entidad (primer proyecto o vacio), rareza certificada de ``_entity_param``.
SPEC_GUARDAR = WriterSpec(E.W_GUARDAR, ACTION_WRITE, "documento", "proyecto_id")
SPEC_ADJUNTAR_PDF = WriterSpec(E.W_ADJUNTAR_PDF, ACTION_WRITE, "documento", "documento_id")
SPEC_DEPENDENCIA_DOCUMENTO = WriterSpec(E.W_DEPENDENCIA_DOCUMENTO, ACTION_WRITE, "documento", "documento_id")
SPEC_GUARDAR_DEPENDENCIA = WriterSpec(E.W_GUARDAR_DEPENDENCIA, ACTION_WRITE_INSTITUCION, "dependencia_documental", None)
SPEC_ACTUALIZAR_DEPENDENCIA = WriterSpec(E.W_ACTUALIZAR_DEPENDENCIA, ACTION_WRITE_INSTITUCION, "dependencia_documental",
                                         "dependencia_id")
SPEC_ELIMINAR = WriterSpec(E.W_ELIMINAR, ACTION_DELETE, "documento", "documento_id")
# 6A-B3 (aceptacion humana): vinculo resolucion <-> designacion concreta con los writers YA portados de Designaciones
# (``documentos_respaldo_designaciones``, una designacion -> un acto; un acto -> N designaciones) y su mismo registro
# B10/B12H (``designaciones.service.SPECS``): vincular = documentos.write; quitar = documentos.delete.
SPEC_VINCULAR_DESIGNACIONES = WriterSpec(E.DE.W_VINCULAR_DES_MASIVO, ACTION_WRITE, "acto_administrativo", "documento_id")
SPEC_DESVINCULAR_DESIGNACIONES = WriterSpec(E.DE.W_DESVINCULAR_DES_MASIVO, ACTION_DELETE, "acto_administrativo", None)
CATEGORIA_DESIGNACION = "Designación docente"
# Edicion posterior de las relaciones que cada categoria YA admite al cargarse (docentes / proyectos), con los writers
# del catalogo certificado: agregar docente ``_asegurar_docente_en_documento_v266`` (documentos.write); proyectos
# ``_vincular_proyectos_documento_v261`` (write) y ``desvincular_acto_proyectos_masivo_v267`` (documentos.delete).
SPEC_ASEGURAR_DOCENTE = WriterSpec(E.W_ASEGURAR_DOCENTE, ACTION_WRITE, "documento", "documento_id")
SPEC_VINCULAR_PROYECTOS = WriterSpec(E.W_VINCULAR_PROYECTOS, ACTION_WRITE, "documento", "documento_id")
SPEC_DESVINCULAR_PROYECTOS = WriterSpec(E.W_DESVINCULAR_PROYECTOS, ACTION_DELETE, "acto_administrativo", "documento_id")

# --- textos certificados (entry l. 51514-52129) -------------------------------------------------------------------
TITULO = "📂 Resoluciones y respaldos"
INFO_PAGINA = ("Repositorio documental del departamento. Los actos administrativos pueden registrarse y vincularse aunque "
               "el PDF todavía no esté disponible. Cuando se cuente con el archivo, puede adjuntarse posteriormente sin "
               "perder vínculos ni metadatos. Una misma resolución o disposición puede quedar vinculada a uno o varios "
               "docentes y, cuando corresponda, a uno o varios proyectos.")
TABS = ["📚 Repositorio", "➕ Cargar acto", "🏛️ Dependencias"]
MSG_SIN_DOCUMENTOS = "Todavía no hay documentos respaldatorios cargados en este departamento."
MSG_SIN_COINCIDENCIAS = "No hay documentos que coincidan con los filtros."
MSG_SIN_DEPENDENCIA = "Este documento histórico todavía no tiene una dependencia emisora asignada."
MSG_PDF_PENDIENTE = "PDF pendiente de carga. El acto y sus vínculos ya están registrados."
MSG_PDF_OK = "PDF actualizado correctamente sin modificar el acto ni sus vínculos."
MSG_ELIMINADO = "Acto/documento eliminado del repositorio."
MSG_NO_ELIMINADO = "No se pudo eliminar el documento."
MSG_SOLO_LECTURA = "Tu usuario tiene permisos de solo lectura."
MSG_FALTA_DOCENTE = "Seleccioná al menos un docente para este tipo de resolución."
MSG_FALTA_PROYECTO = "Seleccioná al menos un proyecto para este tipo de documento."
MSG_FALTA_DEPENDENCIA = "Seleccioná la dependencia que emitió esta resolución o disposición."
MSG_SIN_DEPENDENCIAS_ACTIVAS = "No hay dependencias activas. Cargá una en la pestaña 🏛️ Dependencias."
MSG_PDF_GRANDE_ALTA = "El PDF supera 50 MB. Reducí su tamaño antes de cargarlo."
PREFIX_ALTA = "No se pudo guardar el documento: "
MSG_SIN_PERIODO_ACTUAL = "No se pudo identificar el período actual del departamento."
MSG_SIN_PERIODOS = "No hay períodos registrados para consultar."
MSG_SIN_ACTIVOS = "No hay personas con designaciones activas en el período actual."
MSG_SIN_DESIGNACIONES = "No hay personas con designaciones registradas en el período seleccionado."
MSG_SIN_PROYECTOS = "No hay proyectos registrados de ese tipo."
MSG_DEPENDENCIA_AGREGADA = "Dependencia agregada. Ya puede seleccionarse al cargar documentos en cualquier departamento."
MSG_DEPENDENCIA_ACTUALIZADA = "Dependencia actualizada para toda la institución."
MSG_SIN_DEPENDENCIAS = "Todavía no hay dependencias cargadas."
CAPTION_DEPENDENCIAS = ("Este catálogo pertenece a la universidad y se comparte entre todos sus departamentos. Acá se cargan "
                        "los organismos o áreas que pueden emitir resoluciones, disposiciones u otros actos, por ejemplo "
                        "Rectorado, Consejo Superior o Secretaría de Ciencia y Tecnología.")
CAPTION_DOCENTES = "Marcá un solo docente o todos los que correspondan. El PDF se guarda una sola vez."
CAPTION_PROYECTOS = ("Marcá un solo proyecto o todos los que correspondan. El PDF se guarda una sola vez y queda vinculado "
                     "a cada proyecto seleccionado.")
HELP_MODO_DOCENTES = ("La primera opción muestra personas con cualquier designación Activa en el período actual, incluidas "
                      "funciones no docentes. La segunda permite consultar cualquier cuatrimestre y muestra quienes "
                      "tuvieron una designación en ese período.")
HELP_DEPENDENCIA = "Quién emitió la resolución o disposición. El catálogo se administra en la pestaña Dependencias."
MSG_CONFIRMAR_ELIMINAR = "Primero confirmá la eliminación."
# Textos propios de la API (en Streamlit la seleccion sale siempre de la tabla en pantalla).
MSG_DOCUMENTO_NO_ENCONTRADO = "No se encontró el documento seleccionado. Actualizá la pantalla."
MSG_SELECCION_INVALIDA = "La selección no corresponde a las filas mostradas. Actualizá la pantalla."
MSG_VALOR_INVALIDO = "Uno de los valores enviados no es válido para este formulario."
MSG_SIN_ARCHIVO = "El PDF de este acto todavía no fue cargado."
# Hardening NEXT aprobado (D-AK2): firma real del contenido.
MSG_PDF_INVALIDO = ("El archivo seleccionado no es un PDF válido: su contenido no comienza con la firma %PDF-. "
                    "Elegí el PDF original del acto administrativo.")
MSG_INTEGRIDAD = "la base de datos rechazó el cambio por una restricción de unicidad (IntegrityError)."
CAPTION_DESIGNACIONES = ("Marcá la designación o las designaciones concretas que respalda esta resolución. El vínculo se "
                         "guarda por designación y es el que usa la Disposición para tomar el número de resolución.")
MSG_DESIGNACIONES_SOLO_CATEGORIA = "Solo una resolución de “Designación docente” se vincula con designaciones."
MSG_DESIGNACION_YA_VINCULADA = ("Estas designaciones ya están respaldadas por otro acto: {lista}. Confirmá el reemplazo "
                                "del vínculo para que pasen a este acto.")
MSG_SIN_DESIGNACIONES_DOCENTE = "El/los docente/s seleccionado/s no tienen designaciones registradas."
MSG_VINCULOS_SIN_CAMBIOS = "Los vínculos con designaciones no cambiaron."
MSG_DESIGNACION_PENDIENTE = ("Esta resolución todavía no está vinculada a ninguna designación: la relación queda "
                             "pendiente. Podés vincularla desde el detalle del documento en 📚 Repositorio.")
MSG_SIN_DOCENTES_NUEVOS = "Seleccioná al menos un docente que todavía no esté vinculado a este acto."
MSG_SIN_CAMBIOS_PROYECTOS = "Los proyectos vinculados no cambiaron."
MSG_RELACION_NO_ADMITIDA = "Esta categoría de documento no admite esa relación."
MSG_ALTA_SIN_VINCULO = (" El acto quedó guardado, pero NO se pudo vincular a las designaciones: {motivo} Vinculalo desde "
                        "el detalle del documento en 📚 Repositorio.")

# Columnas del listado (sin binario, sin ``usuario_carga`` ni columnas legacy que la pantalla no muestra ni busca).
COLUMNAS_LISTADO = ["id", "fecha", "tipo_documento", "tipo_resolucion", "dependencia_id", "dependencia_emisora",
                    "categoria", "numero", "periodo", "cantidad_docentes", "docentes", "cuiles", "cantidad_proyectos",
                    "proyectos", "proyecto_ids", "referencia", "titulo", "detalle", "observaciones", "archivo_nombre",
                    "archivo_bytes"]
# ``filtrar_dataframe_por_texto`` del buscador (l. 51605-51609).
COLUMNAS_BUSQUEDA = ["tipo_documento", "tipo_resolucion", "dependencia_emisora", "categoria", "numero", "periodo",
                     "docentes", "cuiles", "proyectos", "proyecto_ids", "referencia", "titulo", "detalle",
                     "observaciones", "archivo_nombre"]


class ResolucionesError(Exception):
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
    role: Optional[str]


@dataclass(frozen=True)
class Archivo:
    """Parte ``archivo`` del multipart (D-AK1): nombre y MIME tal como los declaro el navegador + bytes originales."""
    nombre: str
    mime: str
    contenido: bytes


def _id(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ResolucionesError(422, "INVALID", MSG_VALOR_INVALIDO)
    return value


def _texto(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ResolucionesError(422, "INVALID", MSG_VALOR_INVALIDO)
    return value


def _fecha(value: Any) -> date:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        raise ResolucionesError(422, "INVALID", MSG_VALOR_INVALIDO) from None


def _bool(value: Any) -> bool:
    return value is True


def fila_listado(row: dict) -> dict:
    out = {c: _jsonable(row.get(c)) for c in COLUMNAS_LISTADO}
    bytes_pdf = float(pd.to_numeric(pd.Series([row.get("archivo_bytes")]), errors="coerce").fillna(0).iloc[0])
    out["estado_pdf"] = "Adjunto" if bytes_pdf > 0 else "Pendiente"
    out["tamano_kb"] = float(round(pd.Series([bytes_pdf / 1024.0]), 1).iloc[0])
    return out


class ResolucionesService:
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
            raise ResolucionesError(409, "SCOPE_NOT_VERIFIED", scope_message(resolution))
        if not any(m[0] == MODULO for m in visible) or resolution.department is None:
            raise ResolucionesError(409, "SCOPE_INSTITUTIONAL", MSG_INSTITUTIONAL)
        actor = policy.actor_from_session(user, session_scope)
        return Scope(int(resolution.institution["id"]), int(resolution.department["id"]), resolution.institution,
                     resolution.department, actor.role)

    def reader(self, record: SessionRecord) -> Scope:
        scope = self.scope(record)
        actor = policy.actor_from_session(record.user, record.scope)
        decision = policy.decide(actor, ACTION_READ)
        if not decision.allowed:
            raise ResolucionesError(403, "DENIED", denial_message(decision, ACTION_READ))
        return scope

    def _read(self, scope: Scope, fn: Callable[[Lecturas], Any]) -> Any:
        try:
            with self._transaction() as conn:
                conn.execute("SET TRANSACTION READ ONLY")
                repo = DocumentosRepository(conn, scope.institution_id, scope.department_id)
                return fn(Lecturas(repo, self.today(), scope.role))
        except ResolucionesError:
            raise
        except Exception as exc:
            log.error("resoluciones_respaldos: lectura fallida: %s", type(exc).__name__)
            raise ResolucionesError(503, "DB_READ", MSG_DB_READ) from None

    @staticmethod
    def _permisos(record: SessionRecord) -> dict:
        """``can_write()`` / ``can_delete()`` (solo UX, D-AK6): la autoridad es B10 en cada writer."""
        actor = policy.actor_from_session(record.user, record.scope)
        return {"puede_escribir": policy.visual_can(actor, policy.OP_WRITE, DOMINIO),
                "puede_borrar": policy.visual_can(actor, policy.OP_DELETE, DOMINIO)}

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

    def _op(self, record: SessionRecord, scope: Scope, spec: WriterSpec, fn: Callable[[E.Unidad], Any], *,
            entity_raw: Any = None, prefijo: str = "") -> Any:
        """Un writer certificado completo: B10 -> sus COMMITs con SUCCESS, o FAILED (B12I: sin lock ni comparacion optimista)."""
        actor = policy.actor_from_session(record.user, record.scope)
        audit_actor = audit.actor_from_record(record.user, record.scope, record.meta)
        op = audit.Operation(spec.name, spec.action, spec.entity_type, audit_actor, spec.entity_param, entity_raw)
        decision = policy.decide(actor, spec.action)
        if not decision.allowed:
            self._separate(op, audit.OUTCOME_DENIED, error_code=decision.code, metadata={"b10_decision": decision.code})
            raise ResolucionesError(403, "DENIED", denial_message(decision, spec.action), "PermissionError")
        user = record.user
        unidad = E.Unidad(self._transaction, op, scope.institution_id, scope.department_id, today=self.today(),
                          now=self.now(), usuario=str(user.get("email") or user.get("nombre") or "").strip(),
                          usuario_carga=str(user.get("email") or user.get("usuario") or ""))

        def failed(error_code: str) -> None:
            self._separate(op, audit.OUTCOME_FAILED, error_code=error_code,
                           metadata={"coupled_commits": op.coupled_commits})
        try:
            result = fn(unidad)
        except ResolucionesError as exc:
            failed(exc.error_class)
            raise
        except ValueError as exc:
            failed("ValueError")
            raise ResolucionesError(422, "REJECTED", prefijo + str(exc)) from None
        except E.AuditoriaFallida:
            failed("AuditPersistenceError:AUDIT_INSERT_FAILED")
            raise ResolucionesError(503, "AUDIT", f"{audit.MSG_PERSIST} [AUDIT_INSERT_FAILED]",
                                    "AuditPersistenceError") from None
        except psycopg.errors.IntegrityError as exc:
            failed(audit.error_code_of(exc))
            raise ResolucionesError(409, "INTEGRITY", prefijo + MSG_INTEGRIDAD, type(exc).__name__) from None
        except Exception as exc:
            log.error("resoluciones_respaldos: %s falló tras %d COMMIT(s): %s", spec.name, op.coupled_commits,
                      type(exc).__name__)
            failed(audit.error_code_of(exc))
            raise ResolucionesError(503, "DB_ERROR", prefijo + MSG_DB_TRANSACTION, type(exc).__name__) from None
        if op.coupled_commits == 0:
            if not self._separate(op, audit.OUTCOME_SUCCESS,
                                  metadata={"coupled_commits": 0, "post_reason": "NO_POOLED_COMMIT"}):
                raise ResolucionesError(503, "AUDIT", MSG_AUDIT_POST)
        return result

    # ------------------------------------------------------------------ overview (las 3 pestañas)
    def overview(self, record: SessionRecord) -> dict:
        scope = self.reader(record)

        def read(lec: Lecturas) -> dict:
            docs = lec.repositorio()
            deps = lec.dependencias(solo_activas=False)
            activas = lec.dependencias(solo_activas=True)
            periodos = lec.periodos()
            ultimo = lec.ultimo_periodo()
            return {"docs": [] if docs is None or docs.empty else docs.to_dict("records"),
                    "deps": deps.to_dict("records"), "activas": activas, "periodos": periodos, "ultimo": ultimo}

        d = self._read(scope, read)
        filas = [fila_listado(r) for r in d["docs"]]
        df = pd.DataFrame(filas)
        filtros = {"tipos": [], "categorias": [], "dependencias": []}
        if not df.empty:
            filtros = {
                "tipos": ["Todos"] + sorted(df["tipo_documento"].dropna().astype(str).unique().tolist()),
                "categorias": ["Todas"] + sorted(df["categoria"].dropna().astype(str).unique().tolist()),
                "dependencias": ["Todas"] + sorted([x for x in df["dependencia_emisora"].dropna().astype(str).unique()
                                                    .tolist() if str(x).strip()]),
            }
        deps = [{k: _jsonable(r.get(k)) for k in ("id", "nombre", "estado", "observaciones")} for r in d["deps"]]
        activas_count = int(pd.Series([r["estado"] for r in deps], dtype=object).fillna("Activa").astype(str)
                            .eq("Activa").sum()) if deps else 0
        mapa_alta = opciones_dependencias_alta(d["activas"])
        ultimo = d["ultimo"]
        periodo_actual = None if not ultimo or ultimo.get("id") is None else \
            {"id": int(ultimo["id"]), "nombre": str(ultimo.get("nombre") or "período actual")}
        per_docentes = opciones_periodo_docentes(d["periodos"])
        indice = 0
        if periodo_actual is not None:
            for i, pid in enumerate(per_docentes.values()):
                if pid == periodo_actual["id"]:
                    indice = i
                    break
        return {
            "contexto": {"institucion": {"id": scope.institution_id, "nombre": scope.institution.get("nombre")},
                         "departamento": {"id": scope.department_id, "nombre": scope.department.get("nombre")}},
            "titulo": TITULO, "info": INFO_PAGINA, "tabs": TABS, "permisos": self._permisos(record),
            "repositorio": {"filas": filas, "filtros": filtros, "busqueda": COLUMNAS_BUSQUEDA,
                            "vacio": MSG_SIN_DOCUMENTOS if not filas else "", "sin_coincidencias": MSG_SIN_COINCIDENCIAS},
            "alta": {
                "categorias": R.CATEGORIAS_RESPALDO_V249, "tipos": R.TIPOS_DOCUMENTO,
                "categorias_docente": sorted(R.CATEGORIAS_DOCENTE), "categorias_proyecto": sorted(R.CATEGORIAS_PROYECTO),
                "tipos_con_dependencia": sorted(R.TIPOS_CON_DEPENDENCIA),
                "dependencias": [{"etiqueta": k, "id": v[0]} for k, v in mapa_alta.items()],
                "sin_dependencias": MSG_SIN_DEPENDENCIAS_ACTIVAS if len(mapa_alta) == 1 else "",
                "periodos": [{"etiqueta": k, "id": v} for k, v in opciones_periodo_alta(d["periodos"]).items()],
                "modos_docentes": R.MODOS_DOCENTES, "periodo_actual": periodo_actual,
                "periodos_docentes": [{"etiqueta": k, "id": v} for k, v in per_docentes.items()],
                "periodo_docentes_indice": indice, "max_pdf_bytes": R.MAX_PDF_BYTES,
                "textos": {"docentes": CAPTION_DOCENTES, "proyectos": CAPTION_PROYECTOS, "modo": HELP_MODO_DOCENTES,
                           "dependencia": HELP_DEPENDENCIA, "solo_lectura": MSG_SOLO_LECTURA,
                           "falta_docente": MSG_FALTA_DOCENTE, "falta_proyecto": MSG_FALTA_PROYECTO,
                           "falta_dependencia": MSG_FALTA_DEPENDENCIA, "pdf_grande": MSG_PDF_GRANDE_ALTA,
                           "sin_periodo_actual": MSG_SIN_PERIODO_ACTUAL, "sin_periodos": MSG_SIN_PERIODOS,
                           "pdf_invalido": MSG_PDF_INVALIDO},
            },
            "dependencias": {"filas": deps, "activas": activas_count, "cargadas": len(deps),
                             "caption": CAPTION_DEPENDENCIAS, "vacio": MSG_SIN_DEPENDENCIAS if not deps else "",
                             "estados": R.ESTADOS_DEPENDENCIA, "solo_lectura": MSG_SOLO_LECTURA,
                             "opciones_edicion": [{"etiqueta": f"{str(r.get('nombre') or '').strip()} "
                                                               f"[{str(r.get('estado') or 'Activa').strip()}]",
                                                   "id": int(r["id"])} for r in deps]},
        }

    # ------------------------------------------------------------------ 📚 Repositorio: detalle de un documento
    def _documento(self, scope: Scope, documento_id: int) -> dict:
        def read(lec: Lecturas) -> Optional[dict]:
            docs = lec.repositorio()
            if docs is None or docs.empty:
                return None
            fila = next((r for r in docs.to_dict("records") if int(r["id"]) == documento_id), None)
            if fila is None:
                return None
            return {"fila": fila, "tiene_pdf": lec.tiene_pdf(documento_id),
                    "deps": lec.dependencias(solo_activas=False)}

        data = self._read(scope, read)
        if data is None:
            raise ResolucionesError(404, "NOT_FOUND", MSG_DOCUMENTO_NO_ENCONTRADO)
        return data

    def documento(self, record: SessionRecord, data: dict) -> dict:
        scope = self.reader(record)
        did = _id(data.get("id"))
        d = self._documento(scope, did)
        fila = d["fila"]
        opciones, mapa, indice = opciones_dependencias_correccion(d["deps"], fila.get("dependencia_id"))
        dependencia = str(fila.get("dependencia_emisora", "") or "").strip()
        categoria = str(fila.get("categoria") or "")
        es_designacion = categoria == CATEGORIA_DESIGNACION
        designaciones = self._read(scope, lambda lec: self._opciones_designaciones(
            lec, lec.cuiles_documento(did), did)) if es_designacion else []
        tipo_proy = self._tipo_proyecto(categoria)
        proyectos = self._read(scope, lambda lec: self._proyectos_documento(lec, did, tipo_proy)) if tipo_proy else []
        return {
            "designacion_docente": es_designacion, "designaciones": designaciones,
            "caption_designaciones": CAPTION_DESIGNACIONES,
            "designacion_pendiente": MSG_DESIGNACION_PENDIENTE
            if es_designacion and not any(x["vinculada"] for x in designaciones) else "",
            # relaciones que la categoria admite al cargarse (y por lo tanto se pueden revisar despues)
            "relaciones": {"docentes": categoria in R.CATEGORIAS_DOCENTE, "designaciones": es_designacion,
                           "proyectos": tipo_proy or None},
            "proyectos_vinculados": proyectos,
            "fila": fila_listado(fila),
            "encabezado": f"{str(fila.get('tipo_documento', '') or '').strip()} {fila.get('numero', '')}",
            "aviso_dependencia": "" if dependencia else MSG_SIN_DEPENDENCIA,
            "tiene_pdf": d["tiene_pdf"], "pdf_pendiente": "" if d["tiene_pdf"] else MSG_PDF_PENDIENTE,
            "dependencias": [{"etiqueta": e, "id": mapa[e]} for e in opciones], "dependencia_indice": indice,
            "permisos": self._permisos(record),
        }

    def descargar(self, record: SessionRecord, data: dict) -> tuple[bytes, str]:
        """Descarga bajo demanda (D-AK12): reautoriza, re-consulta por id + ambito de la sesion y devuelve el binario."""
        scope = self.reader(record)
        did = _id(data.get("id"))
        pdf = self._read(scope, lambda lec: lec.pdf(did))
        if pdf is None:
            raise ResolucionesError(404, "NOT_FOUND", MSG_DOCUMENTO_NO_ENCONTRADO)
        if not pdf["bytes"]:
            raise ResolucionesError(404, "PDF_PENDIENTE", MSG_SIN_ARCHIVO, tone="warning")
        return pdf["bytes"], pdf["nombre"]

    def _existe(self, scope: Scope, documento_id: int) -> None:
        ids = self._read(scope, lambda lec: {int(r["id"]) for r in lec.repo.documentos_v249().to_dict("records")})
        if documento_id not in ids:
            raise ResolucionesError(404, "NOT_FOUND", MSG_DOCUMENTO_NO_ENCONTRADO)

    def dependencia_documento(self, record: SessionRecord, data: dict) -> dict:
        """"💾 Guardar dependencia del documento" -> ``actualizar_dependencia_documento_v262``."""
        scope = self.reader(record)
        did = _id(data.get("id"))
        dep_id = _id(data.get("dependencia_id"))
        self._existe(scope, did)
        ids = self._read(scope, lambda lec: {int(x) for x in lec.dependencias(solo_activas=False)["id"].tolist()})
        if dep_id not in ids:
            raise ResolucionesError(409, "SELECCION", MSG_SELECCION_INVALIDA)
        nombre = self._op(record, scope, SPEC_DEPENDENCIA_DOCUMENTO,
                          lambda u: E.actualizar_dependencia_documento_v262(u, did, dep_id), entity_raw=did)
        return {"mensaje": f"Dependencia actualizada: {nombre}.", "tono": "success"}

    def adjuntar_pdf(self, record: SessionRecord, data: dict, archivo: Optional[Archivo]) -> dict:
        """"💾 Adjuntar PDF" / "💾 Reemplazar PDF" -> ``adjuntar_pdf_documento_respaldo_v272`` (vacio y > 50 MB los
        rechaza el writer, como el certificado: FAILED)."""
        scope = self.reader(record)
        did = _id(data.get("id"))
        self._existe(scope, did)
        if archivo is None:
            raise ResolucionesError(422, "INVALID", MSG_VALOR_INVALIDO)
        if 0 < len(archivo.contenido) <= R.MAX_PDF_BYTES and not R.es_pdf(archivo.contenido):
            raise ResolucionesError(422, "PDF_INVALIDO", MSG_PDF_INVALIDO)
        self._op(record, scope, SPEC_ADJUNTAR_PDF,
                 lambda u: E.adjuntar_pdf_documento_respaldo_v272(u, did, archivo.nombre, archivo.mime or R.PDF_MIME,
                                                                  archivo.contenido),
                 entity_raw=did)
        return {"mensaje": MSG_PDF_OK, "tono": "success"}

    def eliminar(self, record: SessionRecord, data: dict) -> dict:
        """"🗑️ Eliminar documento" (con confirmacion) -> ``eliminar_documento_respaldo_v251``; delete: solo superadmin."""
        scope = self.reader(record)
        did = _id(data.get("id"))
        self._existe(scope, did)
        if not _bool(data.get("confirmar")):
            raise ResolucionesError(422, "VALIDATION", MSG_CONFIRMAR_ELIMINAR)
        borrados = self._op(record, scope, SPEC_ELIMINAR, lambda u: E.eliminar_documento_respaldo_v251(u, did),
                            entity_raw=did)
        if borrados:
            return {"mensaje": MSG_ELIMINADO, "tono": "success"}
        raise ResolucionesError(409, "NO_ELIMINADO", MSG_NO_ELIMINADO)

    # ------------------------------------------------------------------ ➕ Cargar acto: selectores
    def docentes(self, record: SessionRecord, data: dict) -> dict:
        """Tabla "Docentes alcanzados por la resolución" (l. 51776-51929)."""
        scope = self.reader(record)
        modo = data.get("modo")
        if modo not in R.MODOS_DOCENTES:
            raise ResolucionesError(422, "INVALID", MSG_VALOR_INVALIDO)
        return self._read(scope, lambda lec: self._tabla_docentes(lec, modo, data.get("periodo_id")))

    @staticmethod
    def _tabla_docentes(lec: Lecturas, modo: str, periodo_id: Any) -> dict:
        periodo_filtro, solo_activas, etiqueta, aviso, caption = None, False, "", "", ""
        if modo == R.MODOS_DOCENTES[0]:
            ultimo = lec.ultimo_periodo()
            if ultimo and ultimo.get("id") is not None:
                periodo_filtro, solo_activas = int(ultimo["id"]), True
                etiqueta = str(ultimo.get("nombre") or "período actual")
                caption = (f"Mostrando personas con cualquier designación **Activa** en **{etiqueta}**, incluidas las "
                           "de funciones no docentes.")
            else:
                aviso = MSG_SIN_PERIODO_ACTUAL
        else:
            opciones = opciones_periodo_docentes(lec.periodos())
            if not opciones:
                aviso = MSG_SIN_PERIODOS
            else:
                elegido = next(((k, v) for k, v in opciones.items() if v == periodo_id), None)
                if elegido is None:
                    raise ResolucionesError(409, "SELECCION", MSG_SELECCION_INVALIDA)
                etiqueta, periodo_filtro = elegido
                caption = (f"Mostrando personas que tienen alguna designación registrada en **{etiqueta}**, incluidas "
                           "funciones no docentes, aunque el período hoy sea histórico y esas designaciones se "
                           "visualicen como finalizadas.")
        tabla = lec.docentes_por_periodo_v253(periodo_filtro, solo_activas=solo_activas) \
            if periodo_filtro is not None else pd.DataFrame(columns=["Docente", "CUIL"])
        filas = [{"Docente": str(r["Docente"]), "CUIL": str(r["CUIL"])} for r in tabla.to_dict("records")]
        if not filas and not aviso:
            aviso = MSG_SIN_ACTIVOS if modo == R.MODOS_DOCENTES[0] else MSG_SIN_DESIGNACIONES
        return {"filas": filas, "periodo_id": periodo_filtro, "solo_activas": solo_activas, "caption": caption,
                "aviso": aviso}

    def proyectos(self, record: SessionRecord, data: dict) -> dict:
        """Tabla "Proyectos alcanzados por el documento" (l. 51931-52021)."""
        scope = self.reader(record)
        tipo = data.get("tipo")
        if tipo not in ("extension", "investigacion"):
            raise ResolucionesError(422, "INVALID", MSG_VALOR_INVALIDO)
        filas = self._read(scope, lambda lec: [{k: _jsonable(v) for k, v in r.items()}
                                               for r in lec.proyectos(tipo).to_dict("records")])
        return {"filas": filas, "aviso": "" if filas else MSG_SIN_PROYECTOS}

    # ------------------------------------------------------------------ 6A-B3: designaciones concretas del acto
    @staticmethod
    def _fila_designacion(f: dict, documento_id: Optional[int]) -> dict:
        acto = f.get("acto_documento_id")
        return {"id": int(f["id"]), "cuil": str(f.get("cuil") or ""), "docente": str(f.get("nombre_completo") or ""),
                "periodo": str(f.get("periodo") or ""), "cargo": str(f.get("cargo") or ""),
                "dedicacion": str(f.get("dedicacion") or ""), "tipo_designacion": str(f.get("tipo_designacion") or ""),
                "fecha_desde": f.get("fecha_desde") or "", "fecha_hasta": f.get("fecha_hasta") or "",
                "estado": str(f.get("estado") or ""), "funcion_no_docente": int(f.get("funcion_no_docente") or 0),
                "acto_documento_id": None if acto is None else int(acto),
                "acto_administrativo": str(f.get("acto_administrativo") or ""),
                "vinculada": acto is not None and documento_id is not None and int(acto) == int(documento_id)}

    def _opciones_designaciones(self, lec: Lecturas, cuiles: list, documento_id: Optional[int] = None) -> list[dict]:
        if documento_id is not None:  # tambien los CUIL de designaciones ya vinculadas a este acto (desde Designaciones)
            vinc = lec.repo.vinculos_exactos_v266()
            if vinc is not None and not vinc.empty:
                cuiles = list(cuiles) + [str(c).strip() for c in
                                         vinc[pd.to_numeric(vinc["documento_id"], errors="coerce").eq(documento_id)]
                                         ["cuil"].tolist()]
        filas = [self._fila_designacion(f, documento_id) for f in lec.designaciones_de_docentes(cuiles)]
        return sorted(filas, key=lambda x: (x["docente"], str(x["fecha_desde"]), x["id"]))

    @staticmethod
    def _seleccion_designaciones(data: dict, opciones: list[dict], documento_id: Optional[int]) -> list[int]:
        """Ids reales elegidos: deben ser designaciones listadas; si alguna ya respalda OTRO acto se exige confirmar
        el reemplazo (el writer certificado reasigna: una designacion -> un acto)."""
        sel = data.get("designaciones")
        sel = [] if sel is None else sel
        if not isinstance(sel, list) or any(isinstance(i, bool) or not isinstance(i, int) for i in sel):
            raise ResolucionesError(422, "INVALID", MSG_VALOR_INVALIDO)
        sel = sorted(set(sel))
        por_id = {o["id"]: o for o in opciones}
        if not set(sel) <= set(por_id):
            raise ResolucionesError(409, "SELECCION", MSG_SELECCION_INVALIDA)
        otros = [por_id[i] for i in sel if por_id[i]["acto_documento_id"] is not None
                 and por_id[i]["acto_documento_id"] != documento_id]
        if otros and data.get("reemplazar_vinculos") is not True:
            lista = "; ".join(f"ID {o['id']} ({o['acto_administrativo']})" for o in otros)
            raise ResolucionesError(409, "VINCULO_EXISTENTE", MSG_DESIGNACION_YA_VINCULADA.format(lista=lista),
                                    tone="warning")
        return sel

    def designaciones(self, record: SessionRecord, data: dict) -> dict:
        """Designaciones (todas, de todos los periodos) de los docentes elegidos en ➕ Cargar acto."""
        scope = self.reader(record)
        cuiles = data.get("cuiles") or []
        if not isinstance(cuiles, list) or any(not isinstance(c, str) for c in cuiles):
            raise ResolucionesError(422, "INVALID", MSG_VALOR_INVALIDO)
        filas = self._read(scope, lambda lec: self._opciones_designaciones(lec, cuiles))
        return {"filas": filas, "caption": CAPTION_DESIGNACIONES,
                "aviso": "" if filas or not cuiles else MSG_SIN_DESIGNACIONES_DOCENTE}

    def vincular_designaciones(self, record: SessionRecord, data: dict) -> dict:
        """Detalle de un acto de "Designación docente" ya cargado: fija el conjunto de designaciones que respalda."""
        scope = self.reader(record)
        did = _id(data.get("id"))
        d = self._documento(scope, did)
        if str(d["fila"].get("categoria") or "") != CATEGORIA_DESIGNACION:
            raise ResolucionesError(422, "CATEGORIA", MSG_DESIGNACIONES_SOLO_CATEGORIA)
        opciones = self._read(scope, lambda lec: self._opciones_designaciones(lec, lec.cuiles_documento(did), did))
        sel = set(self._seleccion_designaciones(data, opciones, did))
        actuales = {o["id"] for o in opciones if o["vinculada"]}
        quitar, agregar = sorted(actuales - sel), sorted(sel - actuales)
        if not quitar and not agregar:
            return {"mensaje": MSG_VINCULOS_SIN_CAMBIOS, "tono": "info"}
        if quitar:
            self._op(record, scope, SPEC_DESVINCULAR_DESIGNACIONES,
                     lambda u: E.DE.desvincular_actos_masivo(u, E.DE.W_DESVINCULAR_DES_MASIVO, quitar))
        if agregar:
            self._op(record, scope, SPEC_VINCULAR_DESIGNACIONES,
                     lambda u: E.DE.vincular_actos_masivo(u, E.DE.W_VINCULAR_DES_MASIVO, agregar, did), entity_raw=did)
        return {"mensaje": f"Vínculos actualizados: {len(sel)} designación/es respaldada/s por este acto "
                           f"(+{len(agregar)} / −{len(quitar)}).", "tono": "success"}

    # ------------------------------------------------------------------ 6A-B3: edicion posterior de relaciones
    @staticmethod
    def _tipo_proyecto(categoria: str) -> str:
        if categoria not in R.CATEGORIAS_PROYECTO:
            return ""
        return "extension" if categoria == "Proyecto de Extensión" else "investigacion"

    @staticmethod
    def _proyectos_documento(lec: Lecturas, did: int, tipo: str) -> list[int]:
        """Proyectos del acto: relacion v261; si no tiene ninguna, el ``proyecto_id`` historico (misma regla de
        compatibilidad del listado)."""
        rel = lec.repo.relacion_proyectos()
        if rel is not None and not rel.empty:
            rr = rel[pd.to_numeric(rel["documento_id"], errors="coerce").eq(did)
                     & rel["proyecto_tipo"].astype(str).str.strip().eq(tipo)]
            ids = sorted({int(x) for x in pd.to_numeric(rr["proyecto_id"], errors="coerce").dropna()})
            if ids:
                return ids
        legado = lec.legado_documento(did)
        return [legado["proyecto_id"]] if legado["proyecto_id"] is not None and legado["proyecto_tipo"] == tipo else []

    def agregar_docentes(self, record: SessionRecord, data: dict) -> dict:
        """Agrega docentes a un acto ya cargado (categorias que vinculan docentes), con el mismo selector del alta."""
        scope = self.reader(record)
        did = _id(data.get("id"))
        d = self._documento(scope, did)
        if str(d["fila"].get("categoria") or "") not in R.CATEGORIAS_DOCENTE:
            raise ResolucionesError(422, "CATEGORIA", MSG_RELACION_NO_ADMITIDA)
        modo = data.get("modo")
        sel = data.get("docentes") or []
        if modo not in R.MODOS_DOCENTES or not isinstance(sel, list) or any(not isinstance(c, str) for c in sel):
            raise ResolucionesError(422, "INVALID", MSG_VALOR_INVALIDO)

        def read(lec: Lecturas) -> dict:
            rel = lec.repo.relacion_docentes()
            rel = [] if rel is None or rel.empty else \
                rel[pd.to_numeric(rel["documento_id"], errors="coerce").eq(did)].to_dict("records")
            return {"tabla": self._tabla_docentes(lec, modo, data.get("periodo_id"))["filas"],
                    "rel": [str(r["cuil"]).strip() for r in rel], "legado": lec.legado_documento(did)}

        ctx = self._read(scope, read)
        if not set(sel) <= {f["CUIL"] for f in ctx["tabla"]}:
            raise ResolucionesError(409, "SELECCION", MSG_SELECCION_INVALIDA)
        clave = lambda c: R.clave_cuil(c) or str(c).strip()  # noqa: E731
        actuales = {clave(c) for c in ctx["rel"]}
        legado = ctx["legado"]
        if not actuales and legado["cuil"]:
            actuales.add(clave(legado["cuil"]))
        nuevos = [(f["CUIL"], f["Docente"]) for f in ctx["tabla"] if f["CUIL"] in set(sel) and clave(f["CUIL"]) not in actuales]
        if not nuevos:
            raise ResolucionesError(422, "VALIDATION", MSG_SIN_DOCENTES_NUEVOS)
        # documento historico sin relacion v251: su docente (columna legada) se materializa primero para no ocultarlo
        if not ctx["rel"] and legado["cuil"]:
            nuevos.insert(0, (legado["cuil"], legado["docente"]))

        def fn(u: E.Unidad) -> int:
            return sum(E.asegurar_docente_en_documento_v266(u, did, c, n) for c, n in nuevos)
        self._op(record, scope, SPEC_ASEGURAR_DOCENTE, fn, entity_raw=did)
        return {"mensaje": f"Docentes agregados al acto: {len([c for c in nuevos if clave(c[0]) not in actuales])}.",
                "tono": "success"}

    def vincular_proyectos(self, record: SessionRecord, data: dict) -> dict:
        """Fija los proyectos de un acto de Investigacion / Extension ya cargado (al menos uno, como en el alta)."""
        scope = self.reader(record)
        did = _id(data.get("id"))
        d = self._documento(scope, did)
        tipo = self._tipo_proyecto(str(d["fila"].get("categoria") or ""))
        if not tipo:
            raise ResolucionesError(422, "CATEGORIA", MSG_RELACION_NO_ADMITIDA)
        sel = data.get("proyectos")
        if not isinstance(sel, list) or any(isinstance(i, bool) or not isinstance(i, int) for i in sel):
            raise ResolucionesError(422, "INVALID", MSG_VALOR_INVALIDO)
        if not sel:
            raise ResolucionesError(422, "VALIDATION", MSG_FALTA_PROYECTO)

        def read(lec: Lecturas) -> dict:
            rel = lec.repo.relacion_proyectos()
            rel_ids = set() if rel is None or rel.empty else {
                int(x) for x in pd.to_numeric(rel[pd.to_numeric(rel["documento_id"], errors="coerce").eq(did)
                                                  & rel["proyecto_tipo"].astype(str).str.strip().eq(tipo)]
                                              ["proyecto_id"], errors="coerce").dropna()}
            return {"tabla": lec.proyectos(tipo).to_dict("records"), "rel": rel_ids,
                    "actuales": set(self._proyectos_documento(lec, did, tipo))}

        ctx = self._read(scope, read)
        por_id = {int(f["ID"]): f for f in ctx["tabla"]}
        deseados = set(sel)
        if not deseados <= set(por_id) | ctx["actuales"]:
            raise ResolucionesError(409, "SELECCION", MSG_SELECCION_INVALIDA)
        # agregar lo que falta en la relacion (incluye materializar el proyecto historico que se conserva)
        agregar = sorted(deseados - ctx["rel"])
        quitar = sorted(ctx["actuales"] - deseados)
        if not quitar and not (deseados - ctx["actuales"]):
            return {"mensaje": MSG_SIN_CAMBIOS_PROYECTOS, "tono": "info"}
        if quitar:
            self._op(record, scope, SPEC_DESVINCULAR_PROYECTOS,
                     lambda u: E.desvincular_acto_proyectos_masivo_v267(u, did, tipo, quitar), entity_raw=did)
        if agregar:
            items = [{"tipo": tipo, "id": i, "nombre": str((por_id.get(i) or {}).get("Proyecto") or "").strip(),
                      "codigo": str((por_id.get(i) or {}).get("Código") or "").strip()} for i in agregar]
            self._op(record, scope, SPEC_VINCULAR_PROYECTOS,
                     lambda u: E.vincular_proyectos_documento_v261(u, did, items), entity_raw=did)
        return {"mensaje": f"Proyectos vinculados: {len(deseados)} (+{len(deseados - ctx['actuales'])} / "
                           f"−{len(quitar)}).", "tono": "success"}

    # ------------------------------------------------------------------ ➕ Cargar acto: guardar
    def guardar_acto(self, record: SessionRecord, data: dict, archivo: Optional[Archivo]) -> dict:
        """"💾 Guardar acto respaldatorio" (l. 52048-52079) -> ``guardar_documento_respaldo_v251``."""
        scope = self.reader(record)
        categoria = data.get("categoria")
        tipo_documento = data.get("tipo_documento")
        if categoria not in R.CATEGORIAS_RESPALDO_V249 or tipo_documento not in R.TIPOS_DOCUMENTO:
            raise ResolucionesError(422, "INVALID", MSG_VALOR_INVALIDO)
        numero = _texto(data.get("numero"))
        fecha_doc = _fecha(data.get("fecha"))
        titulo, detalle, observaciones = (_texto(data.get("titulo")), _texto(data.get("detalle")),
                                          _texto(data.get("observaciones")))
        dep_raw = data.get("dependencia_id")
        per_raw = data.get("periodo_id")
        requiere_docentes = categoria in R.CATEGORIAS_DOCENTE
        requiere_proyectos = categoria in R.CATEGORIAS_PROYECTO
        proyecto_tipo = ("extension" if categoria == "Proyecto de Extensión" else "investigacion") \
            if requiere_proyectos else ""

        def read(lec: Lecturas) -> dict:
            out = {"deps": opciones_dependencias_alta(lec.dependencias(solo_activas=True)),
                   "periodos": opciones_periodo_alta(lec.periodos())}
            if requiere_docentes:
                out["docentes"] = self._tabla_docentes(lec, data.get("modo_docentes"), data.get("periodo_docentes_id")) \
                    if data.get("modo_docentes") in R.MODOS_DOCENTES else None
            if requiere_proyectos:
                out["proyectos"] = lec.proyectos(proyecto_tipo).to_dict("records")
            return out

        ctx = self._read(scope, read)
        dependencia_id, dependencia_nombre = None, ""
        if dep_raw is not None:
            par = next((v for v in ctx["deps"].values() if v[0] == _id(dep_raw)), None)
            if par is None:
                raise ResolucionesError(409, "SELECCION", MSG_SELECCION_INVALIDA)
            dependencia_id, dependencia_nombre = par
        periodo_id = None
        if per_raw is not None:
            if _id(per_raw) not in [v for v in ctx["periodos"].values() if v is not None]:
                raise ResolucionesError(409, "SELECCION", MSG_SELECCION_INVALIDA)
            periodo_id = per_raw
        tipo_resolucion = R.tipo_resolucion_legacy_v262(dependencia_nombre) if tipo_documento == "Resolución" else ""

        docentes_relacionados, proyectos_relacionados, proyecto_id, referencia_texto = [], [], None, ""
        if requiere_docentes:
            seleccion = data.get("docentes") or []
            if not isinstance(seleccion, list) or any(not isinstance(c, str) for c in seleccion):
                raise ResolucionesError(422, "INVALID", MSG_VALOR_INVALIDO)
            tabla = (ctx.get("docentes") or {}).get("filas") or []
            if seleccion and not set(seleccion) <= {f["CUIL"] for f in tabla}:
                raise ResolucionesError(409, "SELECCION", MSG_SELECCION_INVALIDA)
            elegidos = set(seleccion)
            docentes_relacionados = [{"cuil": str(f["CUIL"]).strip(), "nombre": str(f["Docente"]).strip()}
                                     for f in tabla if f["CUIL"] in elegidos]
            if docentes_relacionados:
                referencia_texto = f"{categoria}: " + "; ".join(f"{d['nombre']} — CUIL {d['cuil']}"
                                                                for d in docentes_relacionados)
        elif requiere_proyectos:
            seleccion = data.get("proyectos") or []
            if not isinstance(seleccion, list) or any(isinstance(i, bool) or not isinstance(i, int) for i in seleccion):
                raise ResolucionesError(422, "INVALID", MSG_VALOR_INVALIDO)
            tabla = ctx.get("proyectos") or []
            if not set(seleccion) <= {int(f["ID"]) for f in tabla}:
                raise ResolucionesError(409, "SELECCION", MSG_SELECCION_INVALIDA)
            elegidos = set(seleccion)
            proyectos_relacionados = [{"tipo": proyecto_tipo, "id": int(f["ID"]), "nombre": str(f["Proyecto"]).strip(),
                                       "codigo": str(f["Código"]).strip()} for f in tabla if int(f["ID"]) in elegidos]
            if proyectos_relacionados:
                proyecto_id = int(proyectos_relacionados[0]["id"])  # compatibilidad con documentos anteriores
                referencia_texto = f"{categoria}: " + "; ".join(
                    (f"[{p['codigo']}] " if p.get("codigo") else "") + p.get("nombre", "") for p in proyectos_relacionados)

        # Boton deshabilitado del certificado (falta docente / proyecto / dependencia).
        if requiere_docentes and not docentes_relacionados:
            raise ResolucionesError(422, "VALIDATION", MSG_FALTA_DOCENTE)
        if requiere_proyectos and not proyectos_relacionados:
            raise ResolucionesError(422, "VALIDATION", MSG_FALTA_PROYECTO)
        if tipo_documento in R.TIPOS_CON_DEPENDENCIA and dependencia_id is None:
            raise ResolucionesError(422, "VALIDATION", MSG_FALTA_DEPENDENCIA)
        contenido = archivo.contenido if archivo is not None else b""
        if contenido and len(contenido) > R.MAX_PDF_BYTES:
            raise ResolucionesError(422, "VALIDATION", MSG_PDF_GRANDE_ALTA)
        if contenido and not R.es_pdf(contenido):
            raise ResolucionesError(422, "PDF_INVALIDO", MSG_PDF_INVALIDO)
        designaciones_ids: list[int] = []
        if data.get("designaciones"):
            if categoria != CATEGORIA_DESIGNACION:
                raise ResolucionesError(422, "CATEGORIA", MSG_DESIGNACIONES_SOLO_CATEGORIA)
            opciones = self._read(scope, lambda lec: self._opciones_designaciones(
                lec, [d["cuil"] for d in docentes_relacionados]))
            designaciones_ids = self._seleccion_designaciones(data, opciones, None)

        nuevo_id = self._op(record, scope, SPEC_GUARDAR, lambda u: E.guardar_documento_respaldo_v251(
            u, tipo_documento, categoria, numero, fecha_doc, periodo_id, docentes_relacionados, proyecto_tipo,
            proyecto_id, referencia_texto, titulo, detalle, observaciones,
            archivo.nombre if archivo is not None else "", (archivo.mime or R.PDF_MIME) if archivo is not None else "",
            contenido, tipo_resolucion, proyectos_relacionados=proyectos_relacionados, dependencia_id=dependencia_id,
            dependencia_nombre=dependencia_nombre), entity_raw=proyecto_id, prefijo=PREFIX_ALTA)
        cant = len(R.normalizar_docentes_respaldo_v251(docentes_relacionados))
        cant_proy = len(R.normalizar_proyectos_respaldo_v261(proyectos_relacionados, proyecto_tipo))
        sufijo = " PDF pendiente de carga." if not contenido else " PDF adjunto."
        if cant_proy > 1:
            mensaje = f"Acto guardado correctamente (ID {nuevo_id}) y vinculado a {cant_proy} proyectos."
        elif cant_proy == 1:
            mensaje = f"Acto guardado correctamente (ID {nuevo_id}) y vinculado al proyecto seleccionado."
        elif cant > 1:
            mensaje = f"Acto guardado correctamente (ID {nuevo_id}) y vinculado a {cant} docentes."
        elif cant == 1:
            mensaje = f"Acto guardado correctamente (ID {nuevo_id}) y vinculado al docente seleccionado."
        else:
            mensaje = f"Acto guardado correctamente en el repositorio (ID {nuevo_id})."
        tono = "success"
        # aviso aparte (el mensaje certificado del alta no cambia): la relacion con la designacion queda pendiente
        aviso = MSG_DESIGNACION_PENDIENTE if categoria == CATEGORIA_DESIGNACION and not designaciones_ids else ""
        if designaciones_ids:
            try:
                self._op(record, scope, SPEC_VINCULAR_DESIGNACIONES, lambda u: E.DE.vincular_actos_masivo(
                    u, E.DE.W_VINCULAR_DES_MASIVO, designaciones_ids, int(nuevo_id)), entity_raw=int(nuevo_id))
                sufijo += f" Respalda {len(designaciones_ids)} designación/es."
            except ResolucionesError as exc:
                sufijo += MSG_ALTA_SIN_VINCULO.format(motivo=exc.message)
                tono = "warning"
        out = {"mensaje": mensaje + sufijo, "tono": tono, "id": int(nuevo_id)}
        if aviso:
            out["aviso"] = aviso
        return out

    # ------------------------------------------------------------------ 🏛️ Dependencias
    def agregar_dependencia(self, record: SessionRecord, data: dict) -> dict:
        scope = self.reader(record)
        nombre, observaciones = _texto(data.get("nombre")), _texto(data.get("observaciones"))
        self._op(record, scope, SPEC_GUARDAR_DEPENDENCIA,
                 lambda u: E.guardar_dependencia_documental_v262(u, nombre, observaciones))
        return {"mensaje": MSG_DEPENDENCIA_AGREGADA, "tono": "success"}

    def editar_dependencia(self, record: SessionRecord, data: dict) -> dict:
        scope = self.reader(record)
        dep_id = _id(data.get("id"))
        nombre, observaciones = _texto(data.get("nombre")), _texto(data.get("observaciones"))
        estado = data.get("estado")
        if estado not in R.ESTADOS_DEPENDENCIA:
            raise ResolucionesError(422, "INVALID", MSG_VALOR_INVALIDO)
        ids = self._read(scope, lambda lec: {int(x) for x in lec.dependencias(solo_activas=False)["id"].tolist()})
        if dep_id not in ids:
            raise ResolucionesError(409, "SELECCION", MSG_SELECCION_INVALIDA)
        self._op(record, scope, SPEC_ACTUALIZAR_DEPENDENCIA,
                 lambda u: E.actualizar_dependencia_documental_v262(u, dep_id, nombre, estado, observaciones),
                 entity_raw=dep_id)
        return {"mensaje": MSG_DEPENDENCIA_ACTUALIZADA, "tono": "success"}


__all__ = ["ResolucionesService", "ResolucionesError", "Archivo", "fila_listado"]
