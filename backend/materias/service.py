"""Reglas de negocio de Materias (B13-FIX02): carreras/planes, plan de estudio y materias, optativas/electivas.

Alcance (decision humana, docs/estructura_academica_analysis.md §12): las 16 operaciones del modulo certificado
"📚 Materias", alcance INSTITUCION (dominio B10 ``materias``).  Comisiones solo se LEE como guarda institucional.

Cada writer certificado que invoca la UI es una operacion B12H propia (``correlation_id`` por writer), en una
transaccion = un COMMIT certificado:
1. comprobaciones de la UI (campos, confirmaciones, duplicados avisados en pantalla): sin evento;
2. B10 del writer (``materias.write`` / ``materias.delete``, alcance institucion): DENIED;
3. B12I capa U: la fila que el usuario vio (``huella``) se relee fresca; si cambio -> FAILED ``StaleDecisionError``;
4. cuerpo certificado -> SUCCESS ``commit_seq`` 1 en esa transaccion; sin cambios -> SUCCESS POST_OPERATION;
   error -> ROLLBACK + FAILED.
Igual que el certificado: la edicion de materia son DOS writers/COMMITs (comparticion y luego datos) y las cargas
rapidas confirman fila por fila.  La institucion sale SIEMPRE de la sesion revalidada; nunca del cliente.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import logging
import re
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable, Optional

import pandas as pd
from psycopg import Connection

import audit
from auth import policy
from auth.service import AuthService, SessionRecord
from docentes.rules import limpiar_texto_tabla, normalizar_clave
from periodos.service import MSG_AUDIT_POST, MSG_DB_READ, MSG_DB_TRANSACTION, MSG_STALE
from periodos.service import denial_message, scope_message
import uploads

from . import excel, rules
from .repository import MateriasRepository

log = logging.getLogger("deptit_next.materias")

ACTION_READ = policy.Action("materias", policy.OP_READ, policy.SCOPE_INSTITUTION)
ACTION_WRITE = policy.Action("materias", policy.OP_WRITE, policy.SCOPE_INSTITUTION)
ACTION_DELETE = policy.Action("materias", policy.OP_DELETE, policy.SCOPE_INSTITUTION)


@dataclass(frozen=True)
class WriterSpec:
    """Writer del registro B10 (legacy_write_actions.py l. 115-133) y su etiqueta B12H (audit_actor.py)."""
    name: str
    action: policy.Action
    entity_type: str
    entity_param: Optional[str]


W_GUARDAR_CARRERA = WriterSpec("guardar_carrera", ACTION_WRITE, "carrera", None)
W_ACTUALIZAR_CARRERA = WriterSpec("actualizar_carrera", ACTION_WRITE, "carrera", "carrera_id")
W_ELIMINAR_CARRERA = WriterSpec("eliminar_carrera", ACTION_DELETE, "carrera", "carrera_id")
W_GUARDAR_MATERIA = WriterSpec("guardar_materia", ACTION_WRITE, "materia", "carrera_id")
W_ACTUALIZAR_MATERIA = WriterSpec("actualizar_materia", ACTION_WRITE, "materia", "carrera_id")
W_GRILLA_PLAN = WriterSpec("actualizar_codigo_nombre_materias_desde_plan", ACTION_WRITE, "materia", None)
W_COMPARTICION = WriterSpec("guardar_configuracion_comparticion_materia_v137", ACTION_WRITE, "materia", "materia_id")
W_QUITAR = WriterSpec("quitar_materia_del_plan", ACTION_DELETE, "materia", None)
W_ELIMINAR_MATERIA = WriterSpec("eliminar_materia", ACTION_DELETE, "materia", None)
W_LIMPIAR = WriterSpec("limpiar_registros_materias_fuera_del_plan", ACTION_DELETE, "materia", "carrera_id")
W_GUARDAR_OPCION = WriterSpec("guardar_opcion_curricular_v120", ACTION_WRITE, "opcion_curricular", None)
W_ACTUALIZAR_OPCION = WriterSpec("actualizar_opcion_curricular_v120", ACTION_WRITE, "opcion_curricular", "opcion_id")
W_ELIMINAR_OPCION = WriterSpec("eliminar_opcion_curricular_v120", ACTION_DELETE, "opcion_curricular", "opcion_id")
W_AGREGAR_VINCULOS = WriterSpec("agregar_vinculos_opcion_curricular_v120", ACTION_WRITE, "opcion_curricular",
                                "opcion_id")
W_QUITAR_VINCULO = WriterSpec("quitar_vinculo_opcion_curricular_v120", ACTION_DELETE, "opcion_curricular", "opcion_id")
W_CARGAR_EXCEL = WriterSpec("cargar_opciones_curriculares_excel_v124", ACTION_WRITE, "opcion_curricular", None)

# --- textos certificados (entry l. 68554-70014 y funciones citadas en el analisis) -----------------------------
MSG_CARRERA_REQUERIDOS = "Completá al menos Unidad académica, Nombre de la carrera y Plan / versión."
MSG_CARRERA_DUP_ALTA = ("No se guardó la carrera porque ya existe una carrera / plan con esos mismos datos. "
                        "Editá la carrera existente o cambiá los datos si realmente es otro plan.")
MSG_CARRERA_DUP_EDIT = "No se actualizaron los datos porque ya existe otra carrera / plan con esos mismos datos."
MSG_CONFIRMAR = "Primero confirmá la eliminación."
MSG_SIN_CARRERA = "No se encontró la carrera seleccionada."
MSG_ASIGNATURA_REQUERIDA = "Completá al menos el nombre de la asignatura."
MSG_MATERIA_DUP_PLAN = "La materia ya existe en este plan. No se creó una segunda aparición."
MSG_QUITAR_SIN_SELECCION = "Seleccioná al menos una materia."
MSG_QUITAR_CONFIRMAR = "Primero confirmá que querés quitar las materias seleccionadas de este plan."
MSG_CARGA_CONFIRMAR = "Primero confirmá que revisaste la vista previa."
MSG_CARGA_CONFLICTOS = ("Hay conflictos de código. Un mismo código no puede tener nombres distintos dentro de la misma "
                        "universidad.")
MSG_CARGA_DUPLICADAS = ("Hay materias duplicadas. Corregilas antes de cargar; el sistema no permite duplicados dentro "
                        "del mismo plan.")
MSG_CARGA_SIN_FILAS = ("No pude detectar materias válidas. Revisá que la tabla tenga encabezados o que esté pegada con "
                       "columnas separadas.")
MSG_LIMPIEZA_CONFIRMAR = "Primero confirmá la limpieza."
PREFIX_PLAN = "No se pudieron guardar los cambios: "
PREFIX_LIMPIEZA = "No se pudo completar la limpieza: "
PREFIX_EXCEL = "No se pudo procesar el Excel de opciones curriculares: "
MSG_ESPACIOS_SIN_SELECCION = "Marcá al menos un espacio del plan."
MSG_EXCEL_SIN_FILAS = "El archivo no contiene filas completas para cargar."
# Textos propios de la API (casos que la pantalla Streamlit no puede producir o validacion del archivo subido).
MSG_NO_ENCONTRADO = "No se encontró el registro seleccionado. Actualizá la pantalla."
MSG_VALOR_INVALIDO = "Uno de los valores enviados no es válido para este formulario."
MSG_EXCEL_ARCHIVO = "El archivo debe ser un Excel .xlsx válido (hasta 10 MB)."
EXCEL_MAX_BYTES = 10 * 1024 * 1024


class MateriasError(Exception):
    """Error controlado para la UI.  ``error_class`` = clase de la excepcion certificada equivalente (B12H)."""

    def __init__(self, status: int, code: str, message: str, error_class: str = "ValueError"):
        super().__init__(message)
        self.status, self.code, self.message, self.error_class = status, code, message, error_class


@dataclass(frozen=True)
class Scope:
    institution_id: int
    institution: dict
    department: Optional[dict]
    aviso: Optional[str]


def _jsonable(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        f = float(value)
        return int(f) if f.is_integer() else f
    if isinstance(value, float):
        if pd.isna(value):
            return None
        return int(value) if value.is_integer() else value
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        try:
            return _jsonable(value.item())
        except Exception:
            return str(value)
    if value is pd.NA or value is pd.NaT:
        return None
    return value


def _records(df: Optional[pd.DataFrame]) -> list[dict]:
    if df is None or df.empty:
        return []
    return [{str(k): _jsonable(v) for k, v in r.items()} for r in df.to_dict(orient="records")]


def huella(row: dict) -> str:
    raw = json.dumps({k: _jsonable(v) for k, v in row.items() if k != "huella"}, sort_keys=True, ensure_ascii=True,
                     default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _with_huella(rows: list[dict]) -> list[dict]:
    for r in rows:
        r["huella"] = huella(r)
    return rows


def _text(value: Any) -> str:
    """Valor de un ``st.text_input``/``st.text_area``: texto tal cual (sin ``strip``)."""
    return "" if value is None else str(value)


def _int_or_none(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class MateriasService:
    def __init__(self, pool, auth: AuthService, audit_store: audit.AuditStore, *,
                 today: Callable[[], date] = date.today, now: Callable[[], datetime] = datetime.now,
                 transaction: Optional[Callable[[], AbstractContextManager[Connection]]] = None):
        self.auth = auth
        self.audit_store = audit_store
        self.today = today
        self.now = now
        self._transaction = transaction or (lambda: pool.connection(timeout=5))

    # ================================================================== contexto (B12B), lectura y B10
    def scope(self, record: SessionRecord) -> Scope:
        """La fuente de planes es de la INSTITUCION: basta una institucion verificada (B12B ``_pg_conn('planes')``).
        Si la institucion no es verificable, no se muestra ni se opera nada (``SCOPE_DENIED_ID``)."""
        self.auth.apply_default_context(record)
        effective = policy.normalize_role(record.user.get("rol"))
        visible = policy.visible_modules(effective, record.scope.get(policy.DEPARTMENT_SCOPE_KEY))
        resolution = self.auth.resolve_scope(record)
        if resolution.institution is None:
            raise MateriasError(409, "SCOPE_NOT_VERIFIED", scope_message(resolution))
        if not any(m[0] == "materias" for m in visible):
            raise MateriasError(409, "SCOPE_NOT_VERIFIED", scope_message(resolution))
        aviso = scope_message(resolution) if resolution.reason is not None else None
        return Scope(int(resolution.institution["id"]), resolution.institution, resolution.department, aviso)

    def _actor(self, record: SessionRecord) -> policy.ActorContext:
        return policy.actor_from_session(record.user, record.scope)

    def _require_read(self, record: SessionRecord) -> policy.ActorContext:
        actor = self._actor(record)
        decision = policy.decide(actor, ACTION_READ)
        if not decision.allowed:
            raise MateriasError(403, "DENIED", denial_message(decision, ACTION_READ))
        return actor

    def _read(self, scope: Scope, fn: Callable[[MateriasRepository], Any]) -> Any:
        try:
            with self._transaction() as conn:
                conn.execute("SET TRANSACTION READ ONLY")
                return fn(MateriasRepository(conn, scope.institution_id))
        except MateriasError:
            raise
        except Exception as exc:
            log.error("materias: lectura fallida: %s", type(exc).__name__)
            raise MateriasError(503, "DB_READ", MSG_DB_READ) from None

    def _reader(self, record: SessionRecord) -> Scope:
        scope = self.scope(record)
        self._require_read(record)
        return scope

    # ================================================================== B10 + B12H por writer
    def _authorize(self, record: SessionRecord, spec: WriterSpec, entity_raw: Any, prefix: str) -> audit.Operation:
        actor = self._actor(record)
        audit_actor = audit.actor_from_record(record.user, record.scope, record.meta)
        op = audit.Operation(spec.name, spec.action, spec.entity_type, audit_actor, spec.entity_param, entity_raw)
        decision = policy.decide(actor, spec.action)
        if not decision.allowed:
            self._separate(op, audit.OUTCOME_DENIED, error_code=decision.code, metadata={"b10_decision": decision.code})
            raise MateriasError(403, "DENIED", prefix + denial_message(decision, spec.action), "PermissionError")
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

    def _writer(self, record: SessionRecord, scope: Scope, spec: WriterSpec,
                body: Callable[[MateriasRepository], Any], *, entity_raw: Any = None, prefix: str = "",
                stale: Optional[Callable[[], None]] = None, db_prefix: Optional[str] = None) -> Any:
        """Un writer certificado completo: B10 -> B12I (``stale``) -> COMMIT con su SUCCESS, o FAILED."""
        op = self._authorize(record, spec, entity_raw, prefix)
        mutated = False
        try:
            if stale is not None:
                stale()
            with self._transaction() as conn:
                repo = MateriasRepository(conn, scope.institution_id)
                result = body(repo)
                if repo.mutating_statements:
                    try:
                        audit.insert_on(conn, op.event(audit.OUTCOME_SUCCESS, audit.MODE_IN_TRANSACTION, metadata={
                            "commit_seq": 1, "mutating_statements": repo.mutating_statements,
                            "committing_writer": spec.name}))
                    except Exception as exc:
                        log.error("B12H: el evento SUCCESS de %s no pudo insertarse (%s): ROLLBACK", op.name,
                                  audit.error_code_of(exc))
                        raise MateriasError(503, "AUDIT", f"{audit.MSG_PERSIST} [AUDIT_INSERT_FAILED]",
                                            "AuditPersistenceError:AUDIT_INSERT_FAILED") from None
                    mutated = True
        except _Cancel as cancel:
            # ``conn.rollback()`` certificado y retorno normal (False, mensaje): el writer termino sin cambios.
            result, mutated = (False, str(cancel)), False
        except MateriasError as exc:
            self._separate(op, audit.OUTCOME_FAILED, error_code=exc.error_class, metadata={"coupled_commits": 0})
            raise MateriasError(exc.status, exc.code, prefix + exc.message, exc.error_class) from None
        except ValueError as exc:
            # ValueError certificado: la UI muestra str(e).
            self._separate(op, audit.OUTCOME_FAILED, error_code=audit.error_code_of(exc),
                           metadata={"coupled_commits": 0})
            raise MateriasError(409, "REJECTED", prefix + str(exc), type(exc).__name__) from None
        except Exception as exc:
            log.error("materias: %s falló: %s", op.name, type(exc).__name__)
            self._separate(op, audit.OUTCOME_FAILED, error_code=audit.error_code_of(exc),
                           metadata={"coupled_commits": 0})
            raise MateriasError(503, "DB_ERROR", (db_prefix if db_prefix is not None else prefix)
                                + MSG_DB_TRANSACTION) from None
        if not mutated:
            if not self._separate(op, audit.OUTCOME_SUCCESS,
                                  metadata={"coupled_commits": 0, "post_reason": "NO_POOLED_COMMIT"}):
                raise MateriasError(503, "AUDIT", MSG_AUDIT_POST)
        return result

    def _stale(self, scope: Scope, fetch: Callable[[MateriasRepository], Optional[dict]], seen: Any) -> Callable:
        """B12I capa U: relee fresca la fila vista; si no coincide su huella, no se escribe nada."""
        def check() -> None:
            try:
                fila = self._read(scope, fetch)
            except MateriasError:
                raise MateriasError(503, "FRESH_READ", MSG_DB_READ, "FreshReadError") from None
            if fila is None or not isinstance(seen, str) or huella(fila) != seen:
                raise MateriasError(409, "STALE", f"{MSG_STALE} [B12I]", "StaleDecisionError")
        return check

    # ================================================================== lecturas compartidas (certificadas)
    @staticmethod
    def _carreras_df(repo: MateriasRepository, escuela=None, estado=None) -> pd.DataFrame:
        return repo.carreras(escuela=escuela, estado=estado)

    @staticmethod
    def _carrera_row(repo: MateriasRepository, carrera_id: Any) -> Optional[dict]:
        df = repo.carreras()
        if df.empty:
            return None
        fila = df[pd.to_numeric(df["id"], errors="coerce") == _int_or_none(carrera_id)]
        return None if fila.empty else {k: _jsonable(v) for k, v in fila.iloc[0].to_dict().items()}

    @staticmethod
    def _opciones_carreras(repo: MateriasRepository, escuela=None, solo_activas=True) -> dict:
        df = repo.carreras(escuela=escuela, estado="Activa" if solo_activas else None)
        if df.empty:
            return {}
        opciones = {}
        for _, row in df.iterrows():
            plan = row["plan_version"] if pd.notna(row["plan_version"]) and str(row["plan_version"]).strip() \
                else "Sin plan"
            opciones[f"{row['nombre']} — {plan} — {row['escuela']}"] = int(row["id"])
        return opciones

    @staticmethod
    def _plan_todas_row(repo: MateriasRepository, materia_id: Any) -> Optional[dict]:
        df = repo.plan_todas()
        if df.empty:
            return None
        fila = df[pd.to_numeric(df["id"], errors="coerce") == _int_or_none(materia_id)]
        return None if fila.empty else {k: _jsonable(v) for k, v in fila.iloc[0].to_dict().items()}

    @staticmethod
    def _ids_grupo(repo: MateriasRepository, materia_id: Any, incluir_fuera_plan: bool = True) -> list[int]:
        """``_ids_grupo_comparticion_materia_v137``."""
        mid = _int_or_none(materia_id)
        if mid is None:
            return []
        df = repo.plan_todas()
        if df is None or df.empty or "id" not in df.columns:
            return [mid]
        mids = pd.to_numeric(df["id"], errors="coerce").astype("Int64")
        fila = df[mids == mid]
        if fila.empty:
            return [mid]
        if not incluir_fuera_plan and "en_plan" in df.columns:
            df = df[pd.to_numeric(df["en_plan"], errors="coerce").fillna(1).astype(int) == 1].copy()
        clave = rules.clave_materia_conceptual_v137(fila.iloc[0])
        claves = df.apply(rules.clave_materia_conceptual_v137, axis=1)
        ids = pd.to_numeric(df.loc[claves == clave, "id"], errors="coerce").dropna().astype(int).tolist()
        return list(dict.fromkeys(ids or [mid]))

    @staticmethod
    def _apariciones_misma_identidad(repo: MateriasRepository, materia_id: Any, solo_en_plan=True) -> pd.DataFrame:
        """``get_apariciones_misma_identidad_v137``."""
        mid = _int_or_none(materia_id)
        if mid is None:
            return pd.DataFrame()
        df = repo.plan_todas().copy()
        if df.empty:
            return df
        mids = pd.to_numeric(df["id"], errors="coerce").astype("Int64")
        fila = df[mids == mid]
        if fila.empty:
            return pd.DataFrame()
        base = rules.clave_materia_unica_codigo_nombre(fila.iloc[0].get("codigo", ""), fila.iloc[0].get("asignatura", ""))
        claves = df.apply(lambda r: rules.clave_materia_unica_codigo_nombre(r.get("codigo", ""), r.get("asignatura", "")),
                          axis=1)
        out = df[claves == base].copy()
        if solo_en_plan and "en_plan" in out.columns:
            out = out[pd.to_numeric(out["en_plan"], errors="coerce").fillna(1).astype(int) == 1].copy()
        return out.sort_values(["escuela", "carrera", "plan_version", "id"], kind="stable").reset_index(drop=True)

    # --- validaciones certificadas
    @staticmethod
    def existe_carrera_duplicada(repo: MateriasRepository, escuela, codigo, nombre, plan_version,
                                 excluir_id=None) -> pd.DataFrame:
        df = repo.carreras()
        if df.empty:
            return pd.DataFrame()
        df = df.copy()
        if excluir_id is not None:
            df = df[df["id"] != excluir_id].copy()
        escuela_n = normalizar_clave(escuela)
        codigo_n = normalizar_clave(codigo)
        nombre_n = normalizar_clave(nombre)
        plan_n = normalizar_clave(plan_version)
        if not escuela_n or not nombre_n or not plan_n:
            return pd.DataFrame()
        df["_escuela_n"] = df["escuela"].apply(normalizar_clave)
        df["_codigo_n"] = df["codigo"].apply(normalizar_clave)
        df["_nombre_n"] = df["nombre"].apply(normalizar_clave)
        df["_plan_n"] = df["plan_version"].apply(normalizar_clave)
        condicion = (df["_escuela_n"] == escuela_n) & (df["_nombre_n"] == nombre_n) & (df["_plan_n"] == plan_n)
        if codigo_n:
            condicion = condicion & (df["_codigo_n"] == codigo_n)
        return df[condicion].drop(columns=["_escuela_n", "_codigo_n", "_nombre_n", "_plan_n"], errors="ignore")

    @staticmethod
    def existe_materia_duplicada(repo: MateriasRepository, carrera_id, codigo, asignatura, excluir_id=None):
        df = repo.materias_activas_carrera(carrera_id)
        if df.empty:
            return pd.DataFrame()
        codigo_n = rules.normalizar_codigo_materia(codigo)
        asignatura_n = normalizar_clave(asignatura)
        if excluir_id is not None:
            df = df[df["id"] != excluir_id].copy()
        if codigo_n:
            return df[df["codigo"].apply(rules.normalizar_codigo_materia) == codigo_n].copy()
        return df[df["asignatura"].apply(normalizar_clave) == asignatura_n].copy()

    @staticmethod
    def obtener_conflictos_codigo_materia(repo: MateriasRepository, codigo, asignatura, excluir_id=None,
                                          codigo_anterior=None, asignatura_anterior=None) -> pd.DataFrame:
        codigo_n = rules.normalizar_codigo_materia(codigo)
        asignatura_n = normalizar_clave(asignatura)
        if not codigo_n or not asignatura_n:
            return pd.DataFrame()
        df = repo.conflictos_base()
        if df.empty:
            return pd.DataFrame()
        df = df.copy()
        df["_codigo_n"] = df["codigo"].apply(rules.normalizar_codigo_materia)
        df["_asig_n"] = df["asignatura"].apply(normalizar_clave)
        if excluir_id is not None:
            df = df[df["id"] != int(excluir_id)].copy()
        codigo_ant_n = rules.normalizar_codigo_materia(codigo_anterior)
        asig_ant_n = normalizar_clave(asignatura_anterior)
        if codigo_ant_n and asig_ant_n:
            df = df[~((df["_codigo_n"] == codigo_ant_n) & (df["_asig_n"] == asig_ant_n))].copy()
        elif asig_ant_n:
            df = df[df["_asig_n"] != asig_ant_n].copy()
        conflictos = df[(df["_codigo_n"] == codigo_n) & (df["_asig_n"] != asignatura_n)].copy()
        return conflictos.drop(columns=["_codigo_n", "_asig_n"], errors="ignore")

    def validar_codigo_materia_institucional(self, repo, codigo, asignatura, excluir_id=None, codigo_anterior=None,
                                             asignatura_anterior=None) -> None:
        conflictos = self.obtener_conflictos_codigo_materia(repo, codigo, asignatura, excluir_id=excluir_id,
                                                            codigo_anterior=codigo_anterior,
                                                            asignatura_anterior=asignatura_anterior)
        if conflictos.empty:
            return
        codigo_txt = str(codigo or "").strip()
        nombres = sorted(set(conflictos["asignatura"].fillna("").astype(str).str.strip().tolist()))
        nombres = [n for n in nombres if n]
        detalle = " / ".join(nombres[:5])
        if len(nombres) > 5:
            detalle += " / ..."
        raise ValueError(
            f"No se puede guardar la materia. El código {codigo_txt} ya está usado por otra asignatura"
            + (f": {detalle}." if detalle else ".")
            + " Un mismo código no puede corresponder a dos nombres de materia distintos dentro de la misma universidad."
        )

    def validar_cambio_tipo_espacio_opcion_v120(self, repo, codigo_anterior, asignatura_anterior, nuevo_codigo,
                                                nueva_asignatura) -> None:
        cod_ant = rules.normalizar_codigo_materia(codigo_anterior)
        nom_ant = normalizar_clave(asignatura_anterior)
        dfm = repo.materias_codigo_nombre()
        if dfm.empty:
            return
        cods = dfm["codigo"].apply(rules.normalizar_codigo_materia)
        noms = dfm["asignatura"].apply(normalizar_clave)
        mask = ((cods == cod_ant) & (noms == nom_ant)) if cod_ant else (noms == nom_ant)
        ids = pd.to_numeric(dfm.loc[mask, "id"], errors="coerce").dropna().astype(int).tolist()
        if not ids:
            return
        refs = repo.tipos_opciones_de_materias(ids)
        if refs.empty:
            return
        nuevo_tipo = rules.tipo_espacio_curricular_v120(nuevo_codigo, nueva_asignatura)
        tipos = {rules.normalizar_tipo_opcion_v120(x) for x in refs.get("tipo", pd.Series(dtype=str)).tolist()
                 if rules.normalizar_tipo_opcion_v120(x)}
        if not nuevo_tipo or any(t != nuevo_tipo for t in tipos):
            raise ValueError(
                "No se puede convertir este espacio a otro tipo de materia mientras tenga opciones curriculares "
                "habilitadas. Quitá primero esas habilitaciones desde Materias → Optativas / Electivas."
            )

    @staticmethod
    def _ids_referenciados(repo: MateriasRepository, ids_materias) -> set:
        """``_ids_materias_referenciadas_por_comisiones`` (ante una falla de lectura, conserva)."""
        ids = []
        for valor in list(ids_materias or []):
            mid = _int_or_none(valor)
            if mid is not None and mid not in ids:
                ids.append(mid)
        if not ids:
            return set()
        return repo.ids_referenciados(ids)

    # ================================================================== overview
    def overview(self, record: SessionRecord) -> dict:
        scope = self._reader(record)
        actor = self._actor(record)

        def read(repo: MateriasRepository) -> dict:
            carreras = _with_huella(_records(repo.carreras()))
            return {"carreras": carreras, "escuelas": repo.escuelas(), "conteos": repo.conteos(),
                    "opciones_activas": [{"etiqueta": k, "id": v} for k, v in self._opciones_carreras(repo).items()],
                    "opciones_todas": [{"etiqueta": k, "id": v}
                                       for k, v in self._opciones_carreras(repo, solo_activas=False).items()]}

        data = self._read(scope, read)
        return {
            "contexto": {"institucion": {"id": int(scope.institution["id"]), "nombre": scope.institution.get("nombre")},
                         "departamento": ({"id": int(scope.department["id"]), "nombre": scope.department.get("nombre")}
                                          if scope.department else None),
                         "aviso": scope.aviso},
            **data,
            "catalogos": {"anios": rules.ANIOS, "cuatrimestres": rules.CUATRIMESTRES_MAT,
                          "duraciones": rules.DURACIONES, "dictados": rules.DICTADOS,
                          "estados_carrera": rules.ESTADOS_CARRERA, "estados_materia": rules.ESTADOS_MATERIA,
                          "tipos_opcion": rules.TIPOS_OPCION_CURRICULAR, "estados_opcion": rules.ESTADOS_OPCION_CURRICULAR,
                          "comparticion": list(rules.ETIQUETAS_COMPARTICION_MATERIA.items()),
                          "plan_vigente": rules.PLAN_VIGENTE_DEFAULT},
            "permisos": {"puede_escribir": policy.decide(actor, ACTION_WRITE).allowed,
                         "puede_borrar": policy.decide(actor, ACTION_DELETE).allowed},
        }

    # ================================================================== 1. Carreras / planes
    def carreras_consulta(self, record: SessionRecord, data: dict) -> dict:
        scope = self._reader(record)
        escuela = rules.escuela_para_filtro(data.get("escuela"))
        estado = data.get("estado")
        estado = None if estado in (None, "Todos") else estado
        busqueda = _text(data.get("busqueda"))

        def read(repo):
            listado = repo.carreras(escuela=escuela, estado=estado)
            todas = repo.carreras()
            filtrado = todas.copy()
            if busqueda.strip() and not todas.empty:
                q_txt = normalizar_clave(busqueda)
                q_cod = rules.normalizar_codigo_materia(busqueda)

                def coincide(row):
                    for v in [row.get("escuela", ""), row.get("codigo", ""), row.get("nombre", ""),
                              row.get("titulo_otorga", ""), row.get("plan_version", ""), row.get("duracion", ""),
                              row.get("estado", ""), row.get("observaciones", "")]:
                        if q_txt and q_txt in normalizar_clave(v):
                            return True
                        if q_cod and q_cod in rules.normalizar_codigo_materia(v):
                            return True
                    return False

                filtrado = filtrado[filtrado.apply(coincide, axis=1)].copy()
            return {"listado": _records(listado), "edicion": _with_huella(_records(filtrado))}

        return self._read(scope, read)

    def carrera_duplicada(self, record: SessionRecord, data: dict) -> dict:
        scope = self._reader(record)
        e, c, n, p = (_text(data.get(k)) for k in ("escuela", "codigo", "nombre", "plan_version"))
        excluir = _int_or_none(data.get("excluir_id"))
        if not (e and n and p):
            return {"duplicadas": []}
        df = self._read(scope, lambda repo: self.existe_carrera_duplicada(repo, e, c, n, p, excluir_id=excluir))
        return {"duplicadas": _records(df.drop(columns=["id"], errors="ignore") if not df.empty else df)}

    @staticmethod
    def _valores_carrera(data: dict) -> tuple:
        estado = _text(data.get("estado"))
        if estado not in rules.ESTADOS_CARRERA:
            raise MateriasError(422, "INVALID", MSG_VALOR_INVALIDO)
        return (_text(data.get("escuela")), _text(data.get("codigo")), _text(data.get("nombre")),
                _text(data.get("titulo_otorga")), _text(data.get("plan_version")), _text(data.get("duracion")), estado,
                _text(data.get("observaciones")))

    def carrera_alta(self, record: SessionRecord, data: dict) -> dict:
        scope = self.scope(record)
        v = self._valores_carrera(data)
        escuela, codigo, nombre, _, plan = v[0], v[1], v[2], v[3], v[4]
        if not (escuela and nombre and plan):
            raise MateriasError(422, "REQUIRED", MSG_CARRERA_REQUERIDOS)
        dup = self._read(scope, lambda repo: self.existe_carrera_duplicada(repo, escuela, codigo, nombre, plan))
        if not dup.empty:
            raise MateriasError(409, "DUPLICATE", MSG_CARRERA_DUP_ALTA)

        def body(repo):
            # guardar_carrera (l. 14163): vuelve a controlar el duplicado y no crea uno nuevo.
            d = self.existe_carrera_duplicada(repo, escuela, codigo, nombre, plan)
            if not d.empty:
                return int(d.iloc[0]["id"])
            return repo.insert_carrera(list(v))

        self._writer(record, scope, W_GUARDAR_CARRERA, body)
        return {"mensaje": "Carrera / plan registrado correctamente.", "tono": "success"}

    def carrera_editar(self, record: SessionRecord, data: dict) -> dict:
        scope = self.scope(record)
        carrera_id = _int_or_none(data.get("carrera_id"))
        v = self._valores_carrera(data)
        escuela, codigo, nombre, plan = v[0], v[1], v[2], v[4]
        if not escuela or not nombre or not plan:
            raise MateriasError(422, "REQUIRED", MSG_CARRERA_REQUERIDOS)
        dup = self._read(scope, lambda repo: self.existe_carrera_duplicada(repo, escuela, codigo, nombre, plan,
                                                                            excluir_id=carrera_id))
        if not dup.empty:
            raise MateriasError(409, "DUPLICATE", MSG_CARRERA_DUP_EDIT)
        stale = self._stale(scope, lambda repo: self._carrera_row(repo, carrera_id), data.get("huella"))

        def body(repo):
            repo.update_carrera(carrera_id, list(v))
            repo.sync_materias_carrera(carrera_id, escuela, nombre, plan)

        self._writer(record, scope, W_ACTUALIZAR_CARRERA, body, entity_raw=carrera_id, stale=stale)
        return {"mensaje": "Carrera actualizada correctamente.", "tono": "success"}

    def carrera_eliminar(self, record: SessionRecord, data: dict) -> dict:
        scope = self.scope(record)
        carrera_id = _int_or_none(data.get("carrera_id"))
        if data.get("confirmar") is not True:
            raise MateriasError(422, "CONFIRMATION_REQUIRED", MSG_CONFIRMAR)
        eliminar_materias = data.get("eliminar_materias") is True
        stale = self._stale(scope, lambda repo: self._carrera_row(repo, carrera_id), data.get("huella"))

        def body(repo):
            """``eliminar_carrera`` (l. 14204)."""
            if eliminar_materias:
                df_ids = repo.ids_materias_carrera(carrera_id)
                ids = [int(x) for x in pd.to_numeric(df_ids.get("id", pd.Series(dtype=float)), errors="coerce")
                       .dropna().astype(int).unique().tolist()]
                referencias = repo.referencias_comisiones(ids) if ids else 0
                if referencias > 0:
                    raise ValueError(
                        f"No se puede eliminar esta carrera junto con sus materias porque {referencias} comisión(es) "
                        "actual(es) o histórica(s) dependen de esas apariciones del plan. Conservá la carrera/plan "
                        "para mantener la trazabilidad; las materias pueden retirarse del plan sin borrar su historia.")
                if ids:
                    repo.delete_vinculos_materias(ids)
                repo.delete_materias_carrera(carrera_id)
            else:
                if repo.contar_materias_carrera(carrera_id) > 0:
                    raise ValueError("La carrera tiene materias cargadas. Primero eliminá las materias o marcá la "
                                     "opción de eliminarlas junto con la carrera.")
            repo.delete_carrera(carrera_id)

        self._writer(record, scope, W_ELIMINAR_CARRERA, body, entity_raw=carrera_id, stale=stale)
        return {"mensaje": "Carrera eliminada.", "tono": "warning"}

    # ================================================================== 2. Plan de estudio
    def plan(self, record: SessionRecord, data: dict) -> dict:
        scope = self._reader(record)
        carrera_id = _int_or_none(data.get("carrera_id"))
        escuela = rules.escuela_para_filtro(data.get("escuela"))

        def read(repo):
            opciones = self._opciones_carreras(repo, escuela=escuela, solo_activas=True)
            out = {"hay_carreras_activas": not repo.carreras(estado="Activa").empty,
                   "opciones": [{"etiqueta": k, "id": v} for k, v in opciones.items()], "carrera": None, "plan": []}
            if carrera_id is None or carrera_id not in opciones.values():
                return out
            carrera = repo.carrera(carrera_id)
            df_plan = repo.plan(carrera_id)
            out["carrera"] = {k: _jsonable(v) for k, v in (carrera or {}).items()}
            out["plan"] = _with_huella(_records(df_plan))
            if not df_plan.empty:
                out["metricas"] = {
                    "materias": int(len(df_plan)),
                    "horas_totales": int(pd.to_numeric(df_plan["carga_total"], errors="coerce").fillna(0).sum()),
                    "activas": int((df_plan["estado"] == "Activa").sum()),
                    "duracion": (carrera or {}).get("duracion") or "-",
                }
            return out

        return self._read(scope, read)

    def _plan_fila(self, carrera_id: Any, materia_id: Any) -> Callable[[MateriasRepository], Optional[dict]]:
        def fetch(repo):
            df = repo.plan(carrera_id)
            if df.empty:
                return None
            fila = df[pd.to_numeric(df["id"], errors="coerce") == _int_or_none(materia_id)]
            return None if fila.empty else {k: _jsonable(v) for k, v in fila.iloc[0].to_dict().items()}
        return fetch

    def plan_guardar(self, record: SessionRecord, data: dict) -> dict:
        """Grilla del plan: Codigo y Asignatura editables; un unico guardado transaccional por cuadro."""
        scope = self.scope(record)
        carrera_id = _int_or_none(data.get("carrera_id"))
        cambios_in = data.get("cambios") if isinstance(data.get("cambios"), list) else []
        cambios, vistos = [], []
        for c in cambios_in:
            if not isinstance(c, dict) or _int_or_none(c.get("id")) is None:
                raise MateriasError(422, "INVALID", MSG_VALOR_INVALIDO)
            cambios.append({"id": int(c["id"]), "codigo": _text(c.get("codigo")).strip(),
                            "asignatura": _text(c.get("asignatura")).strip()})
            vistos.append((int(c["id"]), c.get("huella")))

        def stale_all() -> None:
            for mid, h in vistos:
                self._stale(scope, self._plan_fila(carrera_id, mid), h)()

        res = self._writer(record, scope, W_GRILLA_PLAN, lambda repo: self._grilla_body(repo, cambios),
                           stale=stale_all if vistos else None, db_prefix=PREFIX_PLAN)
        return {"mensaje": (f"Se actualizaron {res['materias_editadas']} materia(s). "
                            f"Apariciones actualizadas en planes: {res['apariciones_actualizadas']}. "
                            "Las comisiones existentes conservan su materia_id y reflejan el cambio por ID."),
                "tono": "success"}

    def _grilla_body(self, repo: MateriasRepository, cambios: list[dict]) -> dict:
        """``actualizar_codigo_nombre_materias_desde_plan`` (l. 15832, regimen institucional)."""
        if not cambios:
            return {"materias_editadas": 0, "apariciones_actualizadas": 0}
        df_todas = repo.materias_identidad()
        if df_todas.empty:
            raise ValueError("No hay materias cargadas para actualizar.")
        df_final = df_todas.copy()
        df_final["_codigo_n"] = df_final["codigo"].apply(rules.normalizar_codigo_materia)
        df_final["_asig_n"] = df_final["asignatura"].apply(normalizar_clave)
        grupos, ids_actualizados = {}, set()
        for cambio in cambios:
            try:
                id_mat = int(cambio.get("id"))
            except Exception:
                raise ValueError("No se pudo identificar una de las materias editadas.")
            nuevo_codigo = rules.normalizar_codigo_materia(cambio.get("codigo"))
            nueva_asignatura = str(cambio.get("asignatura") or "").strip()
            if not nuevo_codigo:
                raise ValueError("Todas las materias editadas deben tener código.")
            if not nueva_asignatura:
                raise ValueError("Todas las materias editadas deben tener nombre.")
            fila = df_todas[pd.to_numeric(df_todas["id"], errors="coerce").fillna(-1).astype(int) == id_mat]
            if fila.empty:
                raise ValueError(f"No se encontró la materia con ID {id_mat}.")
            codigo_anterior = str(fila.iloc[0].get("codigo") or "").strip()
            asignatura_anterior = str(fila.iloc[0].get("asignatura") or "").strip()
            self.validar_cambio_tipo_espacio_opcion_v120(repo, codigo_anterior, asignatura_anterior, nuevo_codigo,
                                                         nueva_asignatura)
            destino = (nuevo_codigo, nueva_asignatura)
            ids_grupo = self._ids_grupo(repo, id_mat, incluir_fuera_plan=True) or [id_mat]
            clave_grupo = tuple(sorted(int(x) for x in ids_grupo))
            if clave_grupo in grupos and grupos[clave_grupo]["destino"] != destino:
                raise ValueError("La misma materia conceptual fue editada con dos valores distintos en el mismo guardado.")
            grupos[clave_grupo] = {"destino": destino, "ids": ids_grupo, "materia_id_destino": int(id_mat)}
            ids_actualizados.update(ids_grupo)
            mask_final = pd.to_numeric(df_final["id"], errors="coerce").fillna(-1).astype(int).isin(ids_grupo)
            df_final.loc[mask_final, "codigo"] = nuevo_codigo
            df_final.loc[mask_final, "asignatura"] = nueva_asignatura
        df_final["_codigo_n"] = df_final["codigo"].apply(rules.normalizar_codigo_materia)
        df_final["_asig_n"] = df_final["asignatura"].apply(normalizar_clave)
        activos_identidad = df_final[pd.to_numeric(df_final["en_plan"], errors="coerce").fillna(1).astype(int) == 1].copy()
        con_codigo = activos_identidad[activos_identidad["_codigo_n"] != ""].copy()
        for codigo_n, grupo_codigo in con_codigo.groupby("_codigo_n", dropna=False):
            nombres = [n for n in grupo_codigo["_asig_n"].dropna().unique().tolist() if str(n).strip()]
            if len(nombres) > 1:
                codigo_mostrar = str(grupo_codigo.iloc[0].get("codigo") or codigo_n).strip()
                nombres_mostrar = sorted(set(grupo_codigo["asignatura"].fillna("").astype(str).str.strip().tolist()))
                nombres_mostrar = [n for n in nombres_mostrar if n]
                detalle = " / ".join(nombres_mostrar[:5])
                raise ValueError(f"No se puede guardar. El código {codigo_mostrar} quedaría asociado a más de una materia"
                                 + (f": {detalle}." if detalle else "."))
        activos = df_final[pd.to_numeric(df_final["en_plan"], errors="coerce").fillna(1).astype(int) == 1].copy()
        duplicados = activos.groupby(["carrera_id", "_codigo_n", "_asig_n"], dropna=False).size().reset_index(name="n")
        duplicados = duplicados[(duplicados["_codigo_n"] != "") & (duplicados["n"] > 1)]
        if not duplicados.empty:
            for _, d in duplicados.iterrows():
                mask_dup = ((activos["carrera_id"] == d["carrera_id"]) & (activos["_codigo_n"] == d["_codigo_n"])
                            & (activos["_asig_n"] == d["_asig_n"]))
                ids_dup = set(pd.to_numeric(activos.loc[mask_dup, "id"], errors="coerce").dropna().astype(int).tolist())
                if ids_dup & ids_actualizados:
                    raise ValueError("El cambio generaría una materia duplicada dentro del mismo plan de estudios.")
        for info in grupos.values():
            nuevo_codigo, nueva_asignatura = info["destino"]
            for materia_id_grupo in info["ids"]:
                repo.update_codigo_nombre(int(materia_id_grupo), nuevo_codigo, nueva_asignatura)
        return {"materias_editadas": len(grupos), "apariciones_actualizadas": len(ids_actualizados),
                "trazabilidad_por_id": True}

    def _quitar_body(self, materia_id: int, carrera_id_esperada: Optional[int]):
        """``quitar_materia_del_plan`` (l. 16179): (ok, mensaje)."""
        def body(repo):
            fila = repo.materia(materia_id, "id, carrera_id, codigo, asignatura, COALESCE(en_plan, 1) AS en_plan")
            if fila.empty:
                return False, "No se encontró la materia seleccionada."
            carrera_real = _int_or_none(fila.iloc[0].get("carrera_id"))
            if carrera_id_esperada is not None:
                carrera_esperada = int(carrera_id_esperada)
                if carrera_real != carrera_esperada:
                    return False, ("Se canceló la operación por seguridad: la materia seleccionada no pertenece "
                                   "al plan que está abierto. No se modificó ninguna carrera.")
            else:
                carrera_esperada = carrera_real
            if carrera_esperada is None:
                return False, "La materia no tiene una carrera/plan válida asociada."
            if int(fila.iloc[0].get("en_plan") or 0) != 1:
                return False, "No se quitó la materia: ya no formaba parte activa de ese plan."
            mid = int(materia_id)
            if mid in self._ids_referenciados(repo, [mid]):
                if repo.archivar_materia(mid, int(carrera_esperada)) != 1:
                    raise _Cancel("No se pudo archivar exactamente una materia. Se canceló por seguridad.")
                return True, ("Materia quitada únicamente de este plan. Como tiene comisiones históricas, "
                              "se conserva internamente fuera del plan para no romper esa trazabilidad.")
            repo.delete_vinculos_materias([mid])
            if repo.delete_materia_del_plan(mid, int(carrera_esperada)) != 1:
                raise _Cancel("No se pudo eliminar exactamente una materia. Se canceló por seguridad.")
            return True, ("Materia quitada únicamente de este plan y eliminada del registro porque no tenía "
                          "comisiones asociadas. Su código queda disponible.")
        return body

    def _quitar(self, record, scope, materia_id: int, carrera_id: Optional[int], stale=None) -> tuple:
        return self._writer(record, scope, W_QUITAR, self._quitar_body(materia_id, carrera_id), stale=stale)

    def plan_quitar(self, record: SessionRecord, data: dict) -> dict:
        scope = self.scope(record)
        carrera_id = _int_or_none(data.get("carrera_id"))
        seleccion = data.get("materias") if isinstance(data.get("materias"), list) else []
        if not seleccion:
            raise MateriasError(422, "REQUIRED", MSG_QUITAR_SIN_SELECCION)
        if data.get("confirmar") is not True:
            raise MateriasError(422, "CONFIRMATION_REQUIRED", MSG_QUITAR_CONFIRMAR)
        resultados = []
        for item in seleccion:
            mid = _int_or_none(item.get("id")) if isinstance(item, dict) else None
            if mid is None:
                resultados.append((False, f"No se pudo identificar: {item}"))
                continue
            stale = self._stale(scope, self._plan_fila(carrera_id, mid), item.get("huella"))
            resultados.append(self._quitar(record, scope, mid, carrera_id, stale=stale))
        errores = [m for ok, m in resultados if not ok]
        cantidad_ok = sum(1 for ok, _ in resultados if ok)
        out = {"errores": errores, "quitadas": cantidad_ok}
        if errores:
            out["error"] = "No se pudieron quitar todas las materias: " + " | ".join(errores)
        if cantidad_ok:
            out["mensaje"] = f"Se quitaron {cantidad_ok} materia(s) de este plan. El historial se conservó."
        return out

    # ================================================================== 2b. Agregar materia
    def materias_existentes(self, record: SessionRecord, data: dict) -> dict:
        """Modo "Usar materia ya creada": materias de otros planes (o del destino, si se pide) con filtros."""
        scope = self._reader(record)
        destino = _int_or_none(data.get("carrera_id"))

        def read(repo):
            df = rules.asegurar_columnas_materias(repo.plan_todas())
            if data.get("incluir_mismo_plan") is not True and destino is not None:
                df = df[pd.to_numeric(df["carrera_id"], errors="coerce").fillna(-1).astype(int) != int(destino)].copy()
            opciones = {}
            for col in ("escuela", "cuatrimestre", "carrera", "anio", "estado"):
                opciones[col] = sorted([x for x in df[col].apply(rules.valor_limpio_materia).dropna().unique().tolist()
                                        if x]) if not df.empty else []
            filtrado = df.copy()
            for col, todos in (("escuela", "Todas"), ("carrera", "Todas"), ("cuatrimestre", "Todos"), ("anio", "Todos"),
                               ("estado", "Todos")):
                valor = data.get(col)
                if valor not in (None, "", todos):
                    filtrado = filtrado[filtrado[col].apply(rules.valor_limpio_materia) == valor].copy()
            filtrado = rules.filtrar_busqueda_materias(filtrado, _text(data.get("busqueda")), columnas_extra=[
                "carrera", "escuela", "plan_version", "anio", "cuatrimestre", "dictado", "duracion", "estado",
                "observaciones"])
            return {"hay_existentes": not df.empty, "opciones": opciones, "materias": _records(filtrado)}

        return self._read(scope, read)

    def materia_duplicada(self, record: SessionRecord, data: dict) -> dict:
        scope = self._reader(record)
        asignatura = _text(data.get("asignatura"))
        if not asignatura:
            return {"duplicadas": []}
        df = self._read(scope, lambda repo: self.existe_materia_duplicada(
            repo, _int_or_none(data.get("carrera_id")), _text(data.get("codigo")), asignatura))
        return {"duplicadas": _records(df)}

    def _valores_materia(self, data: dict) -> dict:
        """Valores de los widgets del formulario de materia (selectbox / number_input con sus limites)."""
        def entero(nombre, minimo, maximo):
            valor = data.get(nombre)
            if isinstance(valor, bool) or not isinstance(valor, int) or not minimo <= valor <= maximo:
                raise MateriasError(422, "INVALID", MSG_VALOR_INVALIDO)
            return valor
        v = {"codigo": _text(data.get("codigo")), "asignatura": _text(data.get("asignatura")),
             "anio": _text(data.get("anio")), "cuatrimestre": _text(data.get("cuatrimestre")),
             "dictado": _text(data.get("dictado")), "duracion": _text(data.get("duracion")),
             "estado": _text(data.get("estado")), "observaciones": _text(data.get("observaciones")),
             "carga_semanal": entero("carga_semanal", 0, 40), "carga_total": entero("carga_total", 0, 500),
             "orden": entero("orden", 0, 999)}
        if v["anio"] not in rules.ANIOS or v["cuatrimestre"] not in rules.CUATRIMESTRES_MAT \
                or v["dictado"] not in rules.DICTADOS or v["duracion"] not in rules.DURACIONES \
                or v["estado"] not in rules.ESTADOS_MATERIA:
            raise MateriasError(422, "INVALID", MSG_VALOR_INVALIDO)
        return v

    def _guardar_materia_body(self, carrera_id, codigo, asignatura, anio, cuatrimestre, dictado, carga_semanal,
                              carga_total, duracion, estado, observaciones, orden=None):
        """``guardar_materia`` (l. 14696)."""
        def body(repo):
            carrera = repo.carrera(carrera_id)
            if carrera is None:
                raise ValueError(MSG_SIN_CARRERA)
            cod = rules.normalizar_codigo_materia(codigo)
            self.validar_codigo_materia_institucional(repo, cod, asignatura)
            dup = self.existe_materia_duplicada(repo, carrera_id, cod, asignatura)
            if not dup.empty:
                return int(dup.iloc[0]["id"])
            df_previas = repo.materias_archivadas_carrera(carrera_id)
            codigo_n = rules.normalizar_codigo_materia(cod)
            asignatura_n = normalizar_clave(asignatura)
            fila_reactivar = pd.DataFrame()
            if not df_previas.empty:
                if codigo_n:
                    fila_reactivar = df_previas[
                        (df_previas["codigo"].apply(rules.normalizar_codigo_materia) == codigo_n)
                        & (df_previas["asignatura"].apply(normalizar_clave) == asignatura_n)].copy()
                else:
                    fila_reactivar = df_previas[df_previas["asignatura"].apply(normalizar_clave) == asignatura_n].copy()
            if not fila_reactivar.empty:
                id_reactivar = int(fila_reactivar.iloc[0]["id"])
                repo.reactivar_materia(id_reactivar, [cod, asignatura, carrera["nombre"], carrera["escuela"], anio,
                                                      dictado, carga_semanal, carga_total, cuatrimestre, duracion,
                                                      carrera["plan_version"], orden, estado, observaciones])
                return id_reactivar
            return repo.insert_materia([carrera_id, cod, asignatura, carrera["nombre"], carrera["escuela"], anio,
                                        dictado, carga_semanal, carga_total, cuatrimestre, duracion,
                                        carrera["plan_version"], orden, estado, observaciones])
        return body

    def materia_alta(self, record: SessionRecord, data: dict) -> dict:
        scope = self.scope(record)
        carrera_id = _int_or_none(data.get("carrera_id"))
        v = self._valores_materia(data)
        activas = self._read(scope, lambda repo: self._opciones_carreras(repo, solo_activas=True))
        if carrera_id not in activas.values():
            raise MateriasError(409, "NOT_FOUND", MSG_NO_ENCONTRADO)
        if not v["asignatura"]:
            raise MateriasError(422, "REQUIRED", MSG_ASIGNATURA_REQUERIDA)
        dup = self._read(scope, lambda repo: self.existe_materia_duplicada(repo, carrera_id, v["codigo"],
                                                                            v["asignatura"]))
        if not dup.empty:
            raise MateriasError(409, "DUPLICATE", MSG_MATERIA_DUP_PLAN)
        body = self._guardar_materia_body(carrera_id, v["codigo"], v["asignatura"], v["anio"], v["cuatrimestre"],
                                          v["dictado"], v["carga_semanal"], v["carga_total"], v["duracion"], v["estado"],
                                          v["observaciones"], int(v["orden"]) if v["orden"] else None)
        self._writer(record, scope, W_GUARDAR_MATERIA, body, entity_raw=carrera_id)
        return {"mensaje": f"Materia '{v['asignatura']}' agregada correctamente al plan seleccionado.",
                "tono": "success"}

    # ================================================================== 2c. Carga rapida de plan
    def _analizar_carga(self, repo, carrera_id, df_preview, reemplazar) -> dict:
        dup = pd.DataFrame()
        if not reemplazar:
            dup = self._duplicadas_plan(repo, carrera_id, df_preview)
        return {"duplicadas": dup, "conflictos_tabla": rules.detectar_conflictos_codigo_en_tabla(df_preview),
                "conflictos_base": self._conflictos_base(repo, df_preview)}

    def _duplicadas_plan(self, repo, carrera_id, df_plan) -> pd.DataFrame:
        """``detectar_materias_duplicadas_plan`` (l. 8043)."""
        if df_plan is None or df_plan.empty:
            return pd.DataFrame()
        duplicadas, vistas = [], set()
        for idx, row in df_plan.iterrows():
            codigo, asignatura = row.get("codigo", ""), row.get("asignatura", "")
            clave_codigo = rules.normalizar_codigo_materia(codigo)
            clave = clave_codigo if clave_codigo else f"SIN_CODIGO::{normalizar_clave(asignatura)}"
            en_pegado = clave in vistas
            vistas.add(clave)
            dup_base = self.existe_materia_duplicada(repo, carrera_id, codigo, asignatura)
            if not dup_base.empty or en_pegado:
                duplicadas.append({"fila_pegada": int(idx) + 1, "codigo": codigo, "asignatura": asignatura,
                                   "motivo": "Ya existe en esta carrera/plan" if not dup_base.empty
                                   else "Duplicada dentro de la tabla pegada"})
        return pd.DataFrame(duplicadas)

    def _conflictos_base(self, repo, df_plan) -> pd.DataFrame:
        """``detectar_conflictos_codigo_con_base`` (l. 8010)."""
        if df_plan is None or df_plan.empty:
            return pd.DataFrame()
        registros, vistos = [], set()
        for idx, row in df_plan.iterrows():
            codigo = str(row.get("codigo", "") or "").strip()
            asignatura = str(row.get("asignatura", "") or "").strip()
            clave = (rules.normalizar_codigo_materia(codigo), normalizar_clave(asignatura))
            if not clave[0] or not clave[1] or clave in vistos:
                continue
            vistos.add(clave)
            for _, conf in self.obtener_conflictos_codigo_materia(repo, codigo, asignatura).iterrows():
                registros.append({"fila_pegada": int(idx) + 1, "codigo": codigo, "asignatura_a_cargar": asignatura,
                                  "asignatura_existente": conf.get("asignatura", ""),
                                  "carrera_existente": conf.get("carrera", ""),
                                  "plan_existente": conf.get("plan_version", ""),
                                  "motivo": "El código ya existe en la base con otro nombre"})
        return pd.DataFrame(registros)

    def _parse_plan(self, texto: Any) -> pd.DataFrame:
        try:
            return rules.parsear_plan_pegado(_text(texto)) if _text(texto).strip() else pd.DataFrame()
        except Exception as exc:
            log.info("materias: tabla de plan no interpretable: %s", type(exc).__name__)
            raise MateriasError(422, "PARSE", MSG_CARGA_SIN_FILAS) from None

    def carga_preview(self, record: SessionRecord, data: dict) -> dict:
        scope = self._reader(record)
        carrera_id = _int_or_none(data.get("carrera_id"))
        df = self._parse_plan(data.get("texto"))
        if df.empty:
            return {"filas": [], "aviso": MSG_CARGA_SIN_FILAS if _text(data.get("texto")).strip() else None}
        a = self._read(scope, lambda repo: self._analizar_carga(repo, carrera_id, df, data.get("reemplazar") is True))
        return {"filas": _records(df), "duplicadas": _records(a["duplicadas"]),
                "conflictos_tabla": _records(a["conflictos_tabla"]), "conflictos_base": _records(a["conflictos_base"]),
                "aviso": None}

    def carga_ejecutar(self, record: SessionRecord, data: dict) -> dict:
        scope = self.scope(record)
        carrera_id = _int_or_none(data.get("carrera_id"))
        reemplazar = data.get("reemplazar") is True
        df = self._parse_plan(data.get("texto"))
        activas = self._read(scope, lambda repo: self._opciones_carreras(repo, solo_activas=True))
        if carrera_id not in activas.values():
            raise MateriasError(409, "NOT_FOUND", MSG_NO_ENCONTRADO)
        if df.empty:
            raise MateriasError(422, "PARSE", MSG_CARGA_SIN_FILAS)
        if data.get("confirmar") is not True:
            raise MateriasError(422, "CONFIRMATION_REQUIRED", MSG_CARGA_CONFIRMAR)
        a = self._read(scope, lambda repo: self._analizar_carga(repo, carrera_id, df, reemplazar))
        if not a["conflictos_tabla"].empty or not a["conflictos_base"].empty:
            raise MateriasError(422, "CONFLICTS", MSG_CARGA_CONFLICTOS)
        if not a["duplicadas"].empty:
            raise MateriasError(422, "DUPLICATES", MSG_CARGA_DUPLICADAS)
        if reemplazar:
            actuales = self._read(scope, lambda repo: repo.plan(carrera_id))
            errores = []
            for mid in pd.to_numeric(actuales.get("id", pd.Series(dtype=float)), errors="coerce").dropna() \
                    .astype(int).tolist():
                ok, msg = self._quitar(record, scope, int(mid), carrera_id)
                if not ok:
                    errores.append(msg)
            if errores:
                raise MateriasError(409, "REPLACE_INCOMPLETE",
                                    "No se pudo limpiar completamente el plan antes de reemplazarlo: "
                                    + " | ".join(errores[:5]))
        cargadas = 0
        for pos, (_, row) in enumerate(df.iterrows(), start=1):
            body = self._guardar_materia_body(
                carrera_id, row["codigo"], row["asignatura"],
                row["anio"] if row["anio"] in rules.ANIOS else "1° Año",
                row["cuatrimestre"] if row["cuatrimestre"] in rules.CUATRIMESTRES_MAT else "Sin especificar",
                row["dictado"] if row["dictado"] in rules.DICTADOS else "Presencial",
                int(row["carga_semanal"]), int(row["carga_total"]),
                row["duracion"] if row["duracion"] in rules.DURACIONES else "Cuatrimestral",
                "Activa", "", None if pd.isna(row["orden"]) else int(row["orden"]))
            try:
                self._writer(record, scope, W_GUARDAR_MATERIA, body, entity_raw=carrera_id)
            except MateriasError as exc:
                # El certificado no captura la excepcion: las filas anteriores quedan confirmadas.
                raise MateriasError(exc.status, exc.code, (
                    f"La carga se interrumpió en la fila {pos}: {exc.message} Materias ya cargadas antes del error: "
                    f"{cargadas}."), exc.error_class) from None
            cargadas += 1
        return {"mensaje": f"Se cargaron {cargadas} materias en el plan seleccionado.", "tono": "success"}

    # ================================================================== 2d. Editar / eliminar materia
    def materias_consulta(self, record: SessionRecord, data: dict) -> dict:
        scope = self._reader(record)
        carrera_id = _int_or_none(data.get("carrera_id"))
        busqueda = _text(data.get("busqueda"))

        def read(repo):
            if carrera_id is None:
                df = repo.plan_todas()
                if "en_plan" in df.columns:
                    df = df[pd.to_numeric(df["en_plan"], errors="coerce").fillna(1).astype(int) == 1].copy()
            else:
                df = repo.plan(carrera_id)
                todas = repo.plan_todas()
                extra = todas[["id", "carrera", "escuela", "plan_version"]] if not todas.empty else None
                if extra is not None and not df.empty:
                    df = df.merge(extra, on="id", how="left")
            vacio = df.empty
            if busqueda.strip() and not df.empty:
                q = busqueda.strip().lower()
                df = df[df["codigo"].fillna("").astype(str).str.lower().str.contains(q, na=False, regex=False)
                        | df["asignatura"].fillna("").astype(str).str.lower().str.contains(q, na=False, regex=False)]
            return {"vacio": vacio, "materias": _with_huella(_records(df))}

        return self._read(scope, read)

    def materia_detalle(self, record: SessionRecord, data: dict) -> dict:
        scope = self._reader(record)
        mid = _int_or_none(data.get("id"))

        def read(repo):
            fila = self._plan_todas_row(repo, mid)
            if fila is None:
                raise MateriasError(404, "NOT_FOUND", MSG_NO_ENCONTRADO)
            apariciones = self._apariciones_misma_identidad(repo, mid, solo_en_plan=True)
            cols = [c for c in ["id", "codigo", "asignatura", "carrera", "escuela", "plan_version", "anio",
                                "cuatrimestre", "comparticion_modo", "comparticion_grupo"] if c in apariciones.columns]
            aps = _records(apariciones[cols] if not apariciones.empty else apariciones)
            for a in aps:
                a["etiqueta"] = rules.etiqueta_plan_materia_v137(a)
                a["modo_etiqueta"] = rules.ETIQUETAS_COMPARTICION_MATERIA_INV.get(
                    rules.normalizar_modo_comparticion_v137(a.get("comparticion_modo")), str(a.get("comparticion_modo")))
            fila["huella"] = huella(fila)
            fila["comparticion_modo"] = rules.normalizar_modo_comparticion_v137(fila.get("comparticion_modo"))
            return {"materia": fila, "apariciones": aps}

        return self._read(scope, read)

    def _comparticion_body(self, materia_id: int, modo: str, seleccionados: list):
        """``guardar_configuracion_comparticion_materia_v137`` (l. 27901)."""
        def body(repo):
            mid = int(materia_id)
            modo_n = rules.normalizar_modo_comparticion_v137(modo)
            df_identidad = self._apariciones_misma_identidad(repo, mid, solo_en_plan=False)
            if df_identidad.empty:
                raise ValueError("No se encontraron las apariciones de esta materia.")
            ids_identidad = pd.to_numeric(df_identidad["id"], errors="coerce").dropna().astype(int).tolist()
            if mid not in ids_identidad:
                ids_identidad.append(mid)
            if modo_n == rules.MODO_COMPARTICION_AUTO:
                for x in ids_identidad:
                    repo.set_comparticion(int(x), rules.MODO_COMPARTICION_AUTO, None)
            elif modo_n == rules.MODO_COMPARTICION_ESPECIFICA:
                actual = repo.comparticion(mid)
                grupo_anterior = str((actual or ("", ""))[1] or "").strip()
                repo.set_comparticion(mid, rules.MODO_COMPARTICION_ESPECIFICA, None)
                if grupo_anterior:
                    restantes = repo.ids_grupo_seleccionado(rules.MODO_COMPARTICION_SELECCIONADA, grupo_anterior)
                    if len(restantes) <= 1:
                        for rid in restantes:
                            repo.set_comparticion(int(rid), rules.MODO_COMPARTICION_ESPECIFICA, None)
            else:
                seleccion = []
                for x in list(seleccionados or []):
                    xi = _int_or_none(x)
                    if xi is not None and xi in ids_identidad and xi not in seleccion:
                        seleccion.append(xi)
                if mid not in seleccion:
                    seleccion.insert(0, mid)
                if len(seleccion) < 2:
                    raise ValueError("Para compartir únicamente entre planes seleccionados, elegí al menos dos "
                                     "apariciones/planes.")
                anterior = repo.comparticion(mid) or (rules.MODO_COMPARTICION_AUTO, "")
                modo_anterior = rules.normalizar_modo_comparticion_v137(anterior[0])
                grupo_anterior = str(anterior[1] or "").strip()
                token_base = f"{repo.inst}|{','.join(map(str, sorted(seleccion)))}"
                grupo = "grp_" + hashlib.sha1(token_base.encode("utf-8")).hexdigest()[:20]
                for x in ids_identidad:
                    xi = int(x)
                    if xi in seleccion:
                        repo.set_comparticion(xi, rules.MODO_COMPARTICION_SELECCIONADA, grupo)
                        continue
                    fila_x = repo.comparticion(xi) or (rules.MODO_COMPARTICION_AUTO, "")
                    modo_x = rules.normalizar_modo_comparticion_v137(fila_x[0])
                    grupo_x = str(fila_x[1] or "").strip()
                    sale_del_grupo_actual = bool(modo_anterior == rules.MODO_COMPARTICION_SELECCIONADA and grupo_anterior
                                                 and modo_x == rules.MODO_COMPARTICION_SELECCIONADA
                                                 and grupo_x == grupo_anterior)
                    if modo_x == rules.MODO_COMPARTICION_AUTO or sale_del_grupo_actual:
                        repo.set_comparticion(xi, rules.MODO_COMPARTICION_ESPECIFICA, None)
            return True
        return body

    def _actualizar_materia_body(self, id_mat, carrera_id, v: dict, orden):
        """``actualizar_materia`` (l. 15619, regimen institucional)."""
        def body(repo):
            carrera = repo.carrera(carrera_id)
            if carrera is None:
                raise ValueError(MSG_SIN_CARRERA)
            codigo = rules.normalizar_codigo_materia(v["codigo"])
            asignatura = v["asignatura"]
            fila_anterior = repo.materia(id_mat)
            codigo_anterior = asignatura_anterior = ""
            if not fila_anterior.empty:
                codigo_anterior = str(fila_anterior.iloc[0].get("codigo") or "").strip()
                asignatura_anterior = str(fila_anterior.iloc[0].get("asignatura") or "").strip()
            ids_propagar = self._ids_grupo(repo, id_mat, incluir_fuera_plan=True)
            self.validar_cambio_tipo_espacio_opcion_v120(repo, codigo_anterior, asignatura_anterior, codigo, asignatura)
            self.validar_codigo_materia_institucional(repo, codigo, asignatura, excluir_id=id_mat,
                                                      codigo_anterior=codigo_anterior,
                                                      asignatura_anterior=asignatura_anterior)
            if not self.existe_materia_duplicada(repo, carrera_id, codigo, asignatura, excluir_id=id_mat).empty:
                raise ValueError("Ese código/materia ya existe dentro de la carrera/plan seleccionado. "
                                 "No se creó una segunda aparición.")
            repo.update_materia(id_mat, [carrera_id, codigo, asignatura, carrera["nombre"], carrera["escuela"],
                                         v["anio"], v["dictado"], v["carga_semanal"], v["carga_total"],
                                         v["cuatrimestre"], v["duracion"], carrera["plan_version"], orden, v["estado"],
                                         v["observaciones"]])
            for materia_id_grupo in ids_propagar:
                if int(materia_id_grupo) == int(id_mat):
                    continue
                repo.update_codigo_nombre(int(materia_id_grupo), codigo, asignatura)
        return body

    def materia_editar(self, record: SessionRecord, data: dict) -> dict:
        """Dos writers certificados y dos COMMITs: primero la comparticion, luego los datos de la materia."""
        scope = self.scope(record)
        id_mat = _int_or_none(data.get("id"))
        carrera_id = _int_or_none(data.get("carrera_id"))
        v = self._valores_materia(data)
        etiqueta = data.get("comparticion_modo")
        if etiqueta not in rules.ETIQUETAS_COMPARTICION_MATERIA:  # opciones del selectbox certificado
            raise MateriasError(422, "INVALID", MSG_VALOR_INVALIDO)
        modo = rules.ETIQUETAS_COMPARTICION_MATERIA[etiqueta]
        todas = self._read(scope, lambda repo: self._opciones_carreras(repo, solo_activas=False))
        if carrera_id not in todas.values():
            raise MateriasError(409, "NOT_FOUND", MSG_NO_ENCONTRADO)
        seleccion = [x for x in (data.get("seleccionados") or []) if _int_or_none(x) is not None] \
            if isinstance(data.get("seleccionados"), list) else []
        if id_mat is not None and id_mat not in [int(x) for x in seleccion]:
            seleccion.insert(0, id_mat)
        stale = self._stale(scope, lambda repo: self._plan_todas_row(repo, id_mat), data.get("huella"))
        self._writer(record, scope, W_COMPARTICION, self._comparticion_body(id_mat, modo, seleccion),
                     entity_raw=id_mat, stale=stale)
        orden = int(v["orden"]) if v["orden"] else None
        self._writer(record, scope, W_ACTUALIZAR_MATERIA, self._actualizar_materia_body(id_mat, carrera_id, v, orden),
                     entity_raw=carrera_id)
        return {"mensaje": "Materia actualizada.", "tono": "success"}

    def materia_eliminar(self, record: SessionRecord, data: dict) -> dict:
        scope = self.scope(record)
        id_mat = _int_or_none(data.get("id"))
        if data.get("confirmar") is not True:
            raise MateriasError(422, "CONFIRMATION_REQUIRED", MSG_CONFIRMAR)
        stale = self._stale(scope, lambda repo: self._plan_todas_row(repo, id_mat), data.get("huella"))

        def body(repo):
            """``eliminar_materia`` (l. 16280): todas las apariciones con el mismo codigo + nombre."""
            fila = repo.materia(id_mat, "codigo, asignatura")
            if fila.empty:
                return
            codigo_anterior = str(fila.iloc[0].get("codigo") or "").strip()
            asignatura_anterior = str(fila.iloc[0].get("asignatura") or "").strip()
            if asignatura_anterior:
                df_ids = repo.ids_misma_identidad(codigo_anterior, asignatura_anterior)
            else:
                df_ids = pd.DataFrame({"id": [int(id_mat)]})
            ids = [int(x) for x in pd.to_numeric(df_ids.get("id", pd.Series(dtype=float)), errors="coerce")
                   .dropna().astype(int).unique().tolist()] or [int(id_mat)]
            referencias = repo.referencias_comisiones(ids)
            if referencias > 0:
                raise ValueError(
                    f"No se puede eliminar definitivamente esta materia porque {referencias} comisión(es) "
                    "actual(es) o histórica(s) la referencian. Usá 'Quitar materias de este plan' para retirarla "
                    "del plan sin romper la trazabilidad.")
            repo.delete_vinculos_materias(ids)
            repo.delete_materias_identidad(codigo_anterior, asignatura_anterior, id_mat)

        self._writer(record, scope, W_ELIMINAR_MATERIA, body, stale=stale)
        return {"mensaje": "Materia eliminada del sistema.", "tono": "warning"}

    # ================================================================== 2e. Materias totales y unicas
    def totales(self, record: SessionRecord, data: dict) -> dict:
        scope = self._reader(record)
        escuela = rules.escuela_para_filtro(data.get("escuela"))
        carrera_id = _int_or_none(data.get("carrera_id"))

        def read(repo):
            fuente = rules.asegurar_columnas_materias(repo.plan_todas())
            en_plan = pd.to_numeric(fuente["en_plan"], errors="coerce").fillna(1).astype(int)
            base, fuera = fuente[en_plan == 1].copy(), fuente[en_plan == 0].copy()
            opciones = rules.opciones_carrera_plan_desde_materias(
                rules.filtrar_materias_dataframe(base, escuela=escuela))
            cid = carrera_id if carrera_id in opciones.values() else None
            estado = data.get("estado")
            cuat = data.get("cuatrimestre")
            df = rules.filtrar_materias_dataframe(
                base, escuela=escuela, carrera_id=cid,
                estado=None if estado in (None, "Todos") else estado,
                cuatrimestre=None if cuat in (None, "Todos") else cuat).drop(columns=["orden", "en_plan"],
                                                                              errors="ignore")
            df = rules.filtrar_busqueda_materias(df, _text(data.get("busqueda")),
                                                 columnas_extra=["carrera", "escuela", "plan_version"])
            out = {"materias": _records(df), "total_base": int(len(base)),
                   "opciones_carrera": [{"etiqueta": k, "id": v} for k, v in opciones.items()],
                   "hay_fuera_plan": not fuera.empty, "archivadas": []}
            if cid is not None:
                arch = rules.filtrar_materias_dataframe(fuera, carrera_id=cid)
                cols = [c for c in ["id", "codigo", "asignatura", "anio", "cuatrimestre", "estado"] if c in arch.columns]
                out["archivadas"] = _records(arch[cols] if not arch.empty else arch)
                out["archivadas_huella"] = huella({"ids": [r["id"] for r in out["archivadas"]]})
            return out

        return self._read(scope, read)

    def limpiar_fuera_plan(self, record: SessionRecord, data: dict) -> dict:
        scope = self.scope(record)
        carrera_id = _int_or_none(data.get("carrera_id"))
        if data.get("confirmar") is not True:
            raise MateriasError(422, "CONFIRMATION_REQUIRED", MSG_LIMPIEZA_CONFIRMAR)

        def fetch(repo):
            df = repo.materias_archivadas_carrera(carrera_id, "id") if carrera_id is not None else pd.DataFrame()
            return {"ids": [int(x) for x in df["id"].tolist()]} if not df.empty else {"ids": []}

        stale = self._stale(scope, fetch, data.get("huella"))

        def body(repo):
            """``limpiar_registros_materias_fuera_del_plan`` (l. 16109)."""
            if carrera_id is None:
                raise ValueError("Seleccioná una carrera/plan válida para limpiar sus registros.")
            df = repo.materias_archivadas_carrera(carrera_id, "id, carrera_id, codigo, asignatura")
            if df.empty:
                return {"detectadas": 0, "eliminadas": 0, "con_historial": 0, "ids_eliminados": []}
            ids = [int(x) for x in pd.to_numeric(df["id"], errors="coerce").dropna().astype(int).tolist()]
            referenciadas = self._ids_referenciados(repo, ids)
            borrables = [mid for mid in ids if mid not in referenciadas]
            if borrables:
                repo.delete_vinculos_materias(borrables)
                repo.delete_archivadas(carrera_id, borrables)
            return {"detectadas": len(ids), "eliminadas": len(borrables), "con_historial": len(referenciadas),
                    "ids_eliminados": borrables}

        res = self._writer(record, scope, W_LIMPIAR, body, entity_raw=carrera_id, stale=stale, db_prefix=PREFIX_LIMPIEZA)
        mensajes = []
        if int(res.get("eliminadas", 0) or 0) > 0:
            mensajes.append({"tono": "success", "texto": f"Se eliminaron definitivamente {res['eliminadas']} registro(s) "
                                                         "fuera del plan que no tenían comisiones asociadas."})
        else:
            mensajes.append({"tono": "info", "texto": "No había registros sin historial para eliminar."})
        if int(res.get("con_historial", 0) or 0) > 0:
            mensajes.append({"tono": "info", "texto": f"{res['con_historial']} registro(s) se conservaron únicamente "
                                                      "porque sostienen comisiones históricas. No aparecen en Materias "
                                                      "totales."})
        return {"mensajes": mensajes, "resumen": res}

    def unicas(self, record: SessionRecord, data: dict) -> dict:
        scope = self._reader(record)
        escuela = rules.escuela_para_filtro(data.get("escuela"))
        estado = data.get("estado")
        cuat = data.get("cuatrimestre")

        def read(repo):
            todas = repo.plan_todas()
            base_total = rules.asegurar_columnas_materias(self._totales_df(todas))
            df = self._totales_df(todas, escuela=escuela, estado=None if estado in (None, "Todos") else estado,
                                  cuatrimestre=None if cuat in (None, "Todos") else cuat)
            unicas = rules.materias_unicas(df)
            unicas = rules.filtrar_busqueda_materias(unicas, _text(data.get("busqueda")),
                                                     columnas_extra=["carreras", "escuelas", "planes_version"])
            return {"materias": _records(unicas), "total_fuente": int(len(base_total))}

        return self._read(scope, read)

    @staticmethod
    def _totales_df(todas, escuela=None, carrera_id=None, estado=None, cuatrimestre=None) -> pd.DataFrame:
        """``get_materias_totales`` (l. 14582) sobre ``get_plan_estudio_todas``."""
        df = rules.filtrar_materias_dataframe(todas, escuela=escuela, carrera_id=carrera_id, estado=estado,
                                              cuatrimestre=cuatrimestre)
        if "en_plan" in df.columns:
            df = df[pd.to_numeric(df["en_plan"], errors="coerce").fillna(1).astype(int) == 1].copy()
        return df.drop(columns=["orden", "en_plan"], errors="ignore")

    # ================================================================== 3. Optativas / Electivas
    @staticmethod
    def _espacios(repo, tipo=None, solo_vigentes=True) -> pd.DataFrame:
        """``get_espacios_optativos_electivos_v120`` (l. 12455)."""
        columnas = ["materia_id", "codigo", "asignatura", "tipo_espacio", "carrera_id", "carrera", "escuela",
                    "plan_version", "anio", "cuatrimestre", "estado", "en_plan"]
        df = repo.plan_todas().copy()
        if df is None or df.empty:
            return pd.DataFrame(columns=columnas)
        if "id" in df.columns and "materia_id" not in df.columns:
            df = df.rename(columns={"id": "materia_id"})
        df["tipo_espacio"] = df.apply(lambda r: rules.tipo_espacio_curricular_v120(r.get("codigo", ""),
                                                                                    r.get("asignatura", "")), axis=1)
        df = df[df["tipo_espacio"] != ""].copy()
        if tipo in rules.TIPOS_OPCION_CURRICULAR:
            df = df[df["tipo_espacio"] == tipo].copy()
        if solo_vigentes:
            df = df[pd.to_numeric(df["en_plan"], errors="coerce").fillna(1).astype(int) == 1].copy()
            df = df[df["estado"].fillna("Activa").astype(str).str.strip().str.lower().isin(["", "activa"])].copy()
        for col in columnas:
            if col not in df.columns:
                df[col] = ""
        return df[columnas].sort_values(["tipo_espacio", "escuela", "carrera", "plan_version", "codigo", "asignatura"],
                                        kind="stable").reset_index(drop=True)

    @staticmethod
    def _vinculos_lote(repo, opcion_ids, solo_vigentes=False) -> pd.DataFrame:
        """``_get_vinculos_opciones_lote_v127``."""
        ids = []
        for x in list(opcion_ids or []):
            v = _int_or_none(x)
            if v is not None and v not in ids:
                ids.append(v)
        columnas = ["vinculo_id", "opcion_id", "materia_id", "fecha_vinculacion", "codigo", "asignatura",
                    "tipo_espacio", "carrera_id", "carrera", "escuela", "plan_version", "anio", "cuatrimestre",
                    "estado", "en_plan"]
        if not ids:
            return pd.DataFrame(columns=columnas)
        out = repo.vinculos_lote(ids)
        if out.empty:
            return pd.DataFrame(columns=columnas)
        out["tipo_espacio"] = out.apply(lambda r: rules.tipo_espacio_curricular_v120(r.get("codigo", ""),
                                                                                      r.get("asignatura", "")), axis=1)
        if solo_vigentes:
            en_plan = pd.to_numeric(out["en_plan"], errors="coerce").fillna(1).astype(int)
            estado = out["estado"].fillna("Activa").astype(str).str.strip().str.lower()
            out = out[(en_plan == 1) & estado.isin(["", "activa"])].copy()
        for col in columnas:
            if col not in out.columns:
                out[col] = ""
        return out[columnas].reset_index(drop=True)

    def _opciones_enriquecidas(self, repo, tipo=None, estado=None) -> pd.DataFrame:
        """``_get_opciones_curriculares_v120_no_cache_v127``."""
        df = repo.opciones(tipo=tipo if tipo in rules.TIPOS_OPCION_CURRICULAR else None,
                           estado=estado if estado in rules.ESTADOS_OPCION_CURRICULAR else None)
        for col in ["cantidad_habilitaciones", "destinos", "carreras_habilitadas", "escuelas_destino", "espacios_plan"]:
            df[col] = "" if col != "cantidad_habilitaciones" else 0
        if df.empty:
            return df
        ids = pd.to_numeric(df["id"], errors="coerce").dropna().astype(int).tolist()
        vinculos = self._vinculos_lote(repo, ids, solo_vigentes=True)
        if vinculos.empty:
            return df
        grupos = {int(k): g.copy() for k, g in vinculos.groupby("opcion_id", sort=False)}
        for i, row in df.iterrows():
            vinc = grupos.get(int(row["id"]), pd.DataFrame())
            if vinc.empty:
                continue
            destinos = []
            for _, v in vinc.iterrows():
                partes = []
                carrera = limpiar_texto_tabla(v.get("carrera", ""))
                espacio = limpiar_texto_tabla(v.get("asignatura", ""))
                codigo = limpiar_texto_tabla(v.get("codigo", ""))
                plan = limpiar_texto_tabla(v.get("plan_version", ""))
                if carrera:
                    partes.append(carrera)
                if codigo or espacio:
                    partes.append(f"{codigo} - {espacio}".strip(" -"))
                if plan:
                    partes.append(plan)
                if partes:
                    destinos.append(" · ".join(partes))
            df.at[i, "cantidad_habilitaciones"] = int(len(vinc))
            df.at[i, "destinos"] = " | ".join(destinos)
            df.at[i, "carreras_habilitadas"] = rules.deptit_join_unicos(vinc.get("carrera", pd.Series(dtype=str)).tolist())
            df.at[i, "escuelas_destino"] = rules.deptit_join_unicos(vinc.get("escuela", pd.Series(dtype=str)).tolist())
            df.at[i, "espacios_plan"] = rules.deptit_join_unicos([
                f"{limpiar_texto_tabla(v.get('codigo', ''))} - {limpiar_texto_tabla(v.get('asignatura', ''))}".strip(" -")
                for _, v in vinc.iterrows()])
        return df

    @staticmethod
    def _opcion_fila(opcion_id) -> Callable:
        def fetch(repo):
            op = repo.opcion(int(opcion_id)) if _int_or_none(opcion_id) is not None else None
            return None if op is None else {k: _jsonable(v) for k, v in op.items()}
        return fetch

    def opciones_consulta(self, record: SessionRecord, data: dict) -> dict:
        scope = self._reader(record)

        def read(repo):
            df = self._opciones_enriquecidas(repo, tipo=data.get("tipo"), estado=data.get("estado"))
            df = rules.filtrar_dataframe_por_texto(df, _text(data.get("buscar")), [
                "codigo", "nombre", "escuela_oferente", "tipo", "carreras_habilitadas", "espacios_plan"])
            rows = _records(df)
            base_cols = ["id", "tipo", "codigo", "nombre", "escuela_oferente", "estado", "observaciones",
                         "fecha_creacion", "fecha_actualizacion"]
            for r in rows:
                r["huella"] = huella({k: r.get(k) for k in base_cols})
            return {"opciones": rows}

        return self._read(scope, read)

    def _dup_opcion(self, repo, tipo, codigo, nombre, escuela_oferente="", excluir_id=None) -> pd.DataFrame:
        """``existe_opcion_curricular_duplicada_v120``."""
        df = self._opciones_enriquecidas(repo)
        if df.empty:
            return pd.DataFrame()
        tipo_n = rules.normalizar_tipo_opcion_v120(tipo)
        cod_n = rules.normalizar_codigo_materia(codigo)
        nom_n = normalizar_clave(nombre)
        escuela_n = normalizar_clave(escuela_oferente)
        mask = (df["tipo"].apply(rules.normalizar_tipo_opcion_v120) == tipo_n) & \
            (df["nombre"].apply(normalizar_clave) == nom_n)
        if cod_n:
            mask = mask & (df["codigo"].apply(rules.normalizar_codigo_materia) == cod_n)
        if tipo_n == "Electiva":
            mask = mask & (df["escuela_oferente"].fillna("").apply(normalizar_clave) == escuela_n)
        if excluir_id is not None:
            mask = mask & (pd.to_numeric(df["id"], errors="coerce") != int(excluir_id))
        return df[mask].copy()

    def opcion_alta(self, record: SessionRecord, data: dict) -> dict:
        scope = self.scope(record)
        estado = _text(data.get("estado"))
        if estado not in rules.ESTADOS_OPCION_CURRICULAR:
            raise MateriasError(422, "INVALID", MSG_VALOR_INVALIDO)

        def body(repo):
            """``guardar_opcion_curricular_v120`` (l. 12758)."""
            tipo = rules.normalizar_tipo_opcion_v120(data.get("tipo"))
            nombre = " ".join(str(data.get("nombre") or "").split())
            codigo = str(data.get("codigo") or "").strip()
            escuela = str(data.get("escuela_oferente") or "").strip()
            if tipo not in rules.TIPOS_OPCION_CURRICULAR:
                raise ValueError("Indicá si la opción es Optativa o Electiva.")
            if not nombre:
                raise ValueError("Indicá el nombre de la materia concreta que se ofrece.")
            if tipo == "Electiva" and not escuela:
                raise ValueError("Las Electivas deben indicar la unidad académica oferente.")
            if not self._dup_opcion(repo, tipo, codigo, nombre, escuela_oferente=escuela).empty:
                raise ValueError("Esa opción curricular ya está registrada.")
            ahora = str(self.now())
            return repo.insert_opcion([tipo, codigo, nombre, escuela, estado, _text(data.get("observaciones")), ahora,
                                       ahora])

        oid = self._writer(record, scope, W_GUARDAR_OPCION, body)
        return {"mensaje": f"Opción curricular registrada (ID {oid}). Ahora definí para qué espacios de los planes "
                           "está habilitada.", "tono": "success", "id": oid}

    def opcion_editar(self, record: SessionRecord, data: dict) -> dict:
        scope = self.scope(record)
        oid = _int_or_none(data.get("id"))
        estado = _text(data.get("estado"))
        if oid is None or estado not in rules.ESTADOS_OPCION_CURRICULAR:
            raise MateriasError(422, "INVALID", MSG_VALOR_INVALIDO)
        stale = self._stale(scope, self._opcion_fila(oid), data.get("huella"))

        def body(repo):
            """``actualizar_opcion_curricular_v120`` (l. 12789)."""
            tipo = rules.normalizar_tipo_opcion_v120(data.get("tipo"))
            nombre = " ".join(str(data.get("nombre") or "").split())
            codigo = str(data.get("codigo") or "").strip()
            escuela = str(data.get("escuela_oferente") or "").strip()
            if tipo not in rules.TIPOS_OPCION_CURRICULAR or not nombre:
                raise ValueError("Completá Tipo y Nombre de la opción curricular.")
            if tipo == "Electiva" and not escuela:
                raise ValueError("Las Electivas deben indicar la unidad académica oferente.")
            if not self._dup_opcion(repo, tipo, codigo, nombre, escuela_oferente=escuela, excluir_id=oid).empty:
                raise ValueError("La edición duplicaría otra opción curricular existente.")
            vinc = self._vinculos_lote(repo, [oid], solo_vigentes=False)
            if not vinc.empty:
                tipos_v = set([x for x in vinc.get("tipo_espacio", pd.Series(dtype=str)).dropna().astype(str).tolist()
                               if x])
                if tipos_v and tipos_v != {tipo}:
                    raise ValueError("No se puede cambiar el tipo mientras existan habilitaciones de otro tipo. "
                                     "Quitalas primero.")
            repo.update_opcion(oid, [tipo, codigo, nombre, escuela, estado, _text(data.get("observaciones")),
                                     str(self.now())])

        self._writer(record, scope, W_ACTUALIZAR_OPCION, body, entity_raw=oid, stale=stale)
        return {"mensaje": "Opción curricular actualizada.", "tono": "success"}

    def opcion_eliminar(self, record: SessionRecord, data: dict) -> dict:
        scope = self.scope(record)
        oid = _int_or_none(data.get("id"))
        if data.get("confirmar") is not True:
            raise MateriasError(422, "CONFIRMATION_REQUIRED", MSG_CONFIRMAR)
        stale = self._stale(scope, self._opcion_fila(oid), data.get("huella"))

        def body(repo):
            """``eliminar_opcion_curricular_v120`` (l. 13326)."""
            refs = repo.comisiones_con_opcion(oid)
            if refs > 0:
                raise ValueError(f"No se puede eliminar esta opción porque {refs} comisión(es) actual(es) o "
                                 "histórica(s) la utilizan. Marcala como Inactiva para que no pueda usarse en nuevas "
                                 "comisiones.")
            repo.delete_vinculos_opcion(oid)
            repo.delete_opcion(oid)

        self._writer(record, scope, W_ELIMINAR_OPCION, body, entity_raw=oid, stale=stale)
        return {"mensaje": "Opción curricular eliminada.", "tono": "warning"}

    def habilitaciones(self, record: SessionRecord, data: dict) -> dict:
        scope = self._reader(record)
        oid = _int_or_none(data.get("id"))
        tipo = rules.normalizar_tipo_opcion_v120(data.get("tipo"))

        def read(repo):
            if oid is None or repo.opcion(oid) is None:
                raise MateriasError(404, "NOT_FOUND", MSG_NO_ENCONTRADO)
            vinc = self._vinculos_lote(repo, [oid], solo_vigentes=False)
            espacios = self._espacios(repo, tipo=tipo, solo_vigentes=True)
            existentes = set(pd.to_numeric(vinc.get("materia_id", pd.Series(dtype=float)), errors="coerce")
                             .dropna().astype(int).tolist()) if not vinc.empty else set()
            if not espacios.empty:
                espacios = espacios[~pd.to_numeric(espacios["materia_id"], errors="coerce").fillna(-1).astype(int)
                                    .isin(existentes)].copy()
            escuela = data.get("filtro_escuela")
            if escuela not in (None, "", "Todas") and not espacios.empty:
                espacios = espacios[espacios["escuela"].fillna("").astype(str) == escuela].copy()
            espacios = rules.filtrar_dataframe_por_texto(espacios, _text(data.get("filtro_carrera")),
                                                         ["carrera", "plan_version"])
            espacios = rules.filtrar_dataframe_por_texto(espacios, _text(data.get("filtro_espacio")),
                                                         ["codigo", "asignatura", "anio", "cuatrimestre"])
            return {"vinculos": _records(vinc), "espacios": _records(espacios)}

        return self._read(scope, read)

    def agregar_habilitaciones(self, record: SessionRecord, data: dict) -> dict:
        scope = self.scope(record)
        oid = _int_or_none(data.get("id"))
        materia_ids = data.get("materia_ids") if isinstance(data.get("materia_ids"), list) else []
        if not materia_ids:
            raise MateriasError(422, "REQUIRED", MSG_ESPACIOS_SIN_SELECCION)
        stale = self._stale(scope, self._opcion_fila(oid), data.get("huella"))

        def body(repo):
            """``agregar_vinculos_opcion_curricular_v120`` (l. 12827)."""
            op = repo.opcion(oid) if oid is not None else None
            if not op:
                raise ValueError("No se encontró la opción curricular.")
            tipo = rules.normalizar_tipo_opcion_v120(op.get("tipo"))
            espacios = self._espacios(repo, tipo=tipo, solo_vigentes=True)
            permitidos = set(pd.to_numeric(espacios.get("materia_id", pd.Series(dtype=float)), errors="coerce")
                             .dropna().astype(int).tolist())
            ids = []
            for x in list(materia_ids or []):
                mid = _int_or_none(x)
                if mid is None:
                    continue
                if mid not in permitidos:
                    raise ValueError("Una de las materias seleccionadas no es un espacio vigente compatible con el "
                                     "tipo de opción.")
                if mid not in ids:
                    ids.append(mid)
            if not ids:
                return 0
            prev = repo.materias_de_opcion(oid)
            existentes = set(pd.to_numeric(prev.get("materia_id", pd.Series(dtype=float)), errors="coerce")
                             .dropna().astype(int).tolist())
            agregados = 0
            for mid in ids:
                if mid in existentes:
                    continue
                repo.insert_vinculo(oid, mid, str(self.today()))
                existentes.add(mid)
                agregados += 1
            return agregados

        n = self._writer(record, scope, W_AGREGAR_VINCULOS, body, entity_raw=oid, stale=stale)
        return {"mensaje": f"Se agregaron {n} habilitación(es).", "tono": "success"}

    def quitar_habilitacion(self, record: SessionRecord, data: dict) -> dict:
        scope = self.scope(record)
        oid, mid = _int_or_none(data.get("id")), _int_or_none(data.get("materia_id"))
        if oid is None or mid is None:
            raise MateriasError(422, "INVALID", MSG_VALOR_INVALIDO)
        stale = self._stale(scope, self._opcion_fila(oid), data.get("huella"))
        self._writer(record, scope, W_QUITAR_VINCULO, lambda repo: repo.delete_vinculo(oid, mid), entity_raw=oid,
                     stale=stale)
        return {"mensaje": "Habilitación quitada. Las comisiones ya abiertas no fueron modificadas.", "tono": "success"}

    # --- Excel v124
    def _catalogo_espacios(self, repo, tipo=None, solo_vigentes=True):
        """``_catalogo_espacios_plan_opcion_v124``: (df, etiqueta->id, id->etiqueta)."""
        df = self._espacios(repo, tipo=tipo, solo_vigentes=solo_vigentes).copy()
        if df is None or df.empty:
            return pd.DataFrame(), {}, {}
        df["etiqueta_selector"] = df.apply(rules.etiqueta_espacio_plan_opcion_v124, axis=1)
        df = df[df["etiqueta_selector"].fillna("").astype(str).str.strip() != ""].copy()
        df = df.drop_duplicates(subset=["materia_id"], keep="first").reset_index(drop=True)
        mapa_etiqueta_id = {str(r["etiqueta_selector"]): int(r["materia_id"]) for _, r in df.iterrows()
                            if pd.notna(r.get("materia_id"))}
        return df, mapa_etiqueta_id, {v: k for k, v in mapa_etiqueta_id.items()}

    def modelo_excel(self, record: SessionRecord) -> bytes:
        scope = self._reader(record)

        def read(repo):
            espacios, _, mapa_id_etiqueta = self._catalogo_espacios(repo)
            ops = self._opciones_enriquecidas(repo)
            vinc = {}
            if not ops.empty:
                lote = self._vinculos_lote(repo, ops["id"].tolist(), solo_vigentes=True)
                for oid, g in (lote.groupby("opcion_id", sort=False) if not lote.empty else []):
                    vinc[int(oid)] = pd.to_numeric(g["materia_id"], errors="coerce").dropna().astype(int).tolist()
            return excel.generar_excel_modelo_carga_rapida_opciones_v124(repo.escuelas(), espacios, mapa_id_etiqueta,
                                                                          ops, vinc)

        return self._read(scope, read)

    @staticmethod
    def _decodificar_excel(contenido_b64: Any) -> bytes:
        if not isinstance(contenido_b64, str) or not contenido_b64:
            raise MateriasError(422, "FILE", MSG_EXCEL_ARCHIVO)
        try:
            contenido = base64.b64decode(contenido_b64, validate=True)
        except (binascii.Error, ValueError):
            raise MateriasError(422, "FILE", MSG_EXCEL_ARCHIVO) from None
        if not contenido or len(contenido) > EXCEL_MAX_BYTES or uploads.problema_xlsx(contenido) is not None:
            raise MateriasError(422, "FILE", MSG_EXCEL_ARCHIVO)  # 6A-B1: estructura OOXML/ZIP validada
        return contenido

    def _leer_excel(self, contenido: bytes) -> pd.DataFrame:
        try:
            return rules.leer_excel_carga_rapida_opciones_v124(contenido)
        except ValueError as exc:
            raise MateriasError(422, "EXCEL", str(exc)) from None
        except Exception as exc:
            log.info("materias: Excel de opciones ilegible: %s", type(exc).__name__)
            raise MateriasError(422, "EXCEL", PREFIX_EXCEL + "el archivo no tiene el formato del modelo.") from None

    def excel_preview(self, record: SessionRecord, data: dict) -> dict:
        self._reader(record)
        df = self._leer_excel(self._decodificar_excel(data.get("contenido_b64")))
        if df.empty:
            return {"filas": [], "aviso": MSG_EXCEL_SIN_FILAS}
        return {"filas": _records(df), "aviso": None}

    def excel_cargar(self, record: SessionRecord, data: dict) -> dict:
        scope = self.scope(record)
        df_carga = self._leer_excel(self._decodificar_excel(data.get("contenido_b64")))
        if df_carga.empty:
            raise MateriasError(422, "EXCEL", MSG_EXCEL_SIN_FILAS)
        if data.get("confirmar") is not True:
            raise MateriasError(422, "CONFIRMATION_REQUIRED", MSG_VALOR_INVALIDO)

        def body(repo):
            """``cargar_opciones_curriculares_excel_v124`` (l. 13139)."""
            espacios, mapa_etiqueta_id, _ = self._catalogo_espacios(repo)
            por_id = {}
            for _, r in (espacios.iterrows() if not espacios.empty else []):
                try:
                    por_id[int(r["materia_id"])] = r.to_dict()
                except Exception:
                    pass
            existentes = self._opciones_enriquecidas(repo).copy()
            for col in ["id", "tipo", "codigo", "nombre", "escuela_oferente", "estado", "observaciones"]:
                if col not in existentes.columns:
                    existentes[col] = ""
            hab_cols = sorted([c for c in df_carga.columns if re.fullmatch(r"habilitacion_\d+", str(c))],
                              key=lambda x: int(x.split("_")[-1]))
            errores, grupos = [], {}
            for idx, row in df_carga.iterrows():
                nro = int(idx) + 2
                tipo = rules.normalizar_tipo_opcion_v120(row.get("tipo", ""))
                codigo = limpiar_texto_tabla(row.get("codigo", ""))
                nombre = " ".join(limpiar_texto_tabla(row.get("nombre", "")).split())
                escuela = limpiar_texto_tabla(row.get("escuela_oferente", ""))
                estado_txt = limpiar_texto_tabla(row.get("estado", "")) or "Activa"
                estado = next((e for e in rules.ESTADOS_OPCION_CURRICULAR
                               if normalizar_clave(e) == normalizar_clave(estado_txt)), "")
                obs = limpiar_texto_tabla(row.get("observaciones", ""))
                if tipo not in rules.TIPOS_OPCION_CURRICULAR:
                    errores.append(f"Fila {nro}: Tipo inválido; debe ser Optativa o Electiva.")
                    continue
                if not nombre:
                    errores.append(f"Fila {nro}: falta la materia concreta que se ofrece.")
                    continue
                if not estado:
                    errores.append(f"Fila {nro}: Estado inválido; debe ser Activa o Inactiva.")
                    continue
                if tipo == "Electiva" and not escuela:
                    errores.append(f"Fila {nro}: las Electivas deben indicar la unidad académica oferente.")
                    continue
                materia_ids = []
                for hc in hab_cols:
                    valor = limpiar_texto_tabla(row.get(hc, ""))
                    if not valor:
                        continue
                    mid = mapa_etiqueta_id.get(valor)
                    if mid is None:
                        m = re.search(r"\[ID:(\d+)\]\s*$", valor)
                        if m:
                            mid = int(m.group(1))
                    if mid is None or int(mid) not in por_id:
                        errores.append(f"Fila {nro}: la habilitación '{valor}' no corresponde a un espacio vigente del "
                                       "catálogo actual.")
                        continue
                    if rules.normalizar_tipo_opcion_v120(por_id[int(mid)].get("tipo_espacio", "")) != tipo:
                        errores.append(f"Fila {nro}: la habilitación '{valor}' no corresponde al tipo {tipo}.")
                        continue
                    if int(mid) not in materia_ids:
                        materia_ids.append(int(mid))
                key = (tipo, rules.normalizar_codigo_materia(codigo), normalizar_clave(nombre),
                       normalizar_clave(escuela) if tipo == "Electiva" else "")
                if key not in grupos:
                    grupos[key] = {"filas": [nro], "tipo": tipo, "codigo": codigo, "nombre": nombre,
                                   "escuela_oferente": escuela, "estado": estado, "observaciones": obs,
                                   "materia_ids": list(materia_ids)}
                else:
                    grupos[key]["filas"].append(nro)
                    for mid in materia_ids:
                        if mid not in grupos[key]["materia_ids"]:
                            grupos[key]["materia_ids"].append(mid)
                    if normalizar_clave(grupos[key]["estado"]) != normalizar_clave(estado):
                        errores.append(f"Filas {grupos[key]['filas']}: la misma opción tiene estados diferentes.")
                    if normalizar_clave(grupos[key]["observaciones"]) != normalizar_clave(obs) and obs:
                        errores.append(f"Filas {grupos[key]['filas']}: la misma opción tiene observaciones diferentes.")
            if errores:
                raise ValueError("No se realizó ninguna carga porque se detectaron errores:\n- " + "\n- ".join(errores[:30])
                                 + ("\n- ..." if len(errores) > 30 else ""))
            acciones = []
            for key, g in grupos.items():
                match = rules.buscar_opcion_equivalente_v124(existentes, g["tipo"], g["codigo"], g["nombre"],
                                                             g["escuela_oferente"])
                if len(match) > 1:
                    raise ValueError(f"No se realizó ninguna carga: la opción '{g['nombre']}' coincide con más de un "
                                     "registro existente. Corregí primero esa duplicación en el catálogo.")
                g["opcion_id_existente"] = int(match.iloc[0]["id"]) if len(match) == 1 else None
                acciones.append(g)
                if len(match) == 0:
                    fila_nueva = {"id": -len(acciones), "tipo": g["tipo"], "codigo": g["codigo"], "nombre": g["nombre"],
                                  "escuela_oferente": g["escuela_oferente"], "estado": g["estado"],
                                  "observaciones": g["observaciones"]}
                    existentes = pd.concat([existentes, pd.DataFrame([fila_nueva])], ignore_index=True)
            creadas = reutilizadas = hab_agregadas = 0
            detalles = []
            for g in acciones:
                oid = g.get("opcion_id_existente")
                resultado = "Existente"
                if oid is None:
                    ahora = str(self.now())
                    oid = repo.insert_opcion([g["tipo"], g["codigo"], g["nombre"], g["escuela_oferente"], g["estado"],
                                              g["observaciones"], ahora, ahora])
                    creadas += 1
                    resultado = "Creada"
                else:
                    reutilizadas += 1
                prev = repo.materias_de_opcion(int(oid))
                ya = set(pd.to_numeric(prev.get("materia_id", pd.Series(dtype=float)), errors="coerce")
                         .dropna().astype(int).tolist())
                agregadas_fila = 0
                for mid in g["materia_ids"]:
                    if int(mid) in ya:
                        continue
                    repo.insert_vinculo(int(oid), int(mid), str(self.today()))
                    ya.add(int(mid))
                    agregadas_fila += 1
                    hab_agregadas += 1
                detalles.append({"Filas Excel": ", ".join(map(str, g["filas"])), "Resultado": resultado,
                                 "ID opción": int(oid), "Tipo": g["tipo"], "Código": g["codigo"],
                                 "Opción concreta": g["nombre"], "Unidad académica oferente": g["escuela_oferente"],
                                 "Habilitaciones solicitadas": len(g["materia_ids"]),
                                 "Habilitaciones nuevas": agregadas_fila})
            return {"opciones_creadas": creadas, "opciones_reutilizadas": reutilizadas,
                    "habilitaciones_agregadas": hab_agregadas, "detalle": detalles}

        res = self._writer(record, scope, W_CARGAR_EXCEL, body, db_prefix=PREFIX_EXCEL)
        return {"mensaje": (f"Carga completada: {res['opciones_creadas']} opción(es) creada(s), "
                            f"{res['opciones_reutilizadas']} existente(s) reutilizada(s) y "
                            f"{res['habilitaciones_agregadas']} habilitación(es) nueva(s)."),
                "tono": "success", "detalle": res["detalle"]}


class _Cancel(Exception):
    """Cancelacion de seguridad de ``quitar_materia_del_plan`` (``conn.rollback()`` + ``(False, mensaje)``)."""
