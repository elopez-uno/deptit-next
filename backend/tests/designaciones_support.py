"""Soporte de los tests de Designaciones.

- Reutiliza de ``periodos_support`` la conexion real que NUNCA confirma (``db_conn``), los SAVEPOINT y la auditoria
  falsa para DENIED/FAILED/POST_OPERATION; de ``materias_support`` el inyector efectivo (v193 + B12J).
- ``certified_designaciones``: funciones del entry certificado (AST, sin modificar reference_fix02, sin bytecode)
  reencadenadas en el MISMO orden de redefinicion del entry (base -> v95 -> v162 -> v233 ...) y ejecutadas sobre la
  base real con las dos conexiones certificadas: ``get_conn()`` (inyector B12B/B12J) y ``_pg_raw_conn()`` (sin
  inyector).  Ambas enlazan los parametros del lado del cliente (``psycopg.ClientCursor``), como psycopg2.
  Sus COMMIT son RELEASE SAVEPOINT dentro de la transaccion del test, que se revierte al terminar.  Cada COMMIT con
  sentencias mutantes registra (commit_seq, mutating_statements, committing_writer = writer de negocio mas interno,
  nested_system_task = tarea de sistema en curso), igual que el acoplamiento B12H.
- La compuerta B12F se reproduce: las reconciliaciones solo corren dentro de un writer de negocio.
- Datos temporales: CUIL sinteticos ``20-9911xxxx-x`` (verificados libres) y filas que se revierten; las secuencias
  pueden avanzar (documentado).
"""

from __future__ import annotations

import ast
import itertools
import json
import re
import sys
from datetime import date, datetime
from io import BytesIO
from pathlib import Path

import pandas as pd
import psycopg
import pytest
from psycopg.rows import dict_row

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

from docentes_support import _StStub, _top_assign  # noqa: E402
from materias_support import planes_injector  # noqa: E402
from periodos_support import (  # noqa: E402,F401  (fixtures re-exportados)
    ENTRY, EXTRA_DEPARTMENTS, FIXED_TODAY, READONLY_QUERIES, FakeAuditStore, _FixedDate, _tree, audit_store, db_conn,
    savepoint, session_for, sql_constants,
)

FIXED_NOW = datetime(2026, 10, 26, 10, 30, 0)
USER_EMAIL = "info@test.local"

BUSINESS = ("guardar_designacion", "actualizar_designacion", "actualizar_designacion_por_error", "eliminar_designacion",
            "eliminar_designaciones_por_error_masivo", "finalizar_designacion_anticipadamente",
            "actualizar_resolucion_fechas_designacion_directo_v171",
            "_limpiar_metadatos_finalizacion_si_reactivada_v233", "registrar_movimiento",
            "sincronizar_movimiento_baja_designacion_v207", "vincular_acto_designacion_v266",
            "vincular_acto_movimiento_v266", "vincular_acto_designaciones_masivo_v267",
            "desvincular_acto_designaciones_masivo_v267", "vincular_acto_movimientos_masivo_v267",
            "desvincular_acto_movimientos_masivo_v267")
SYSTEM = ("sincronizar_cargos_asignaciones_docente_periodo", "_finalizar_comisiones_si_sin_designacion_docente_v214")


class _FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return FIXED_NOW


class _St(_StStub):
    warnings: list = []

    @staticmethod
    def warning(msg, *a, **k):
        _St.warnings.append(str(msg))


_SP = itertools.count(1)


class _Frames:
    def __init__(self):
        self.stack: list[tuple[str, str]] = []
        self.commits: list[dict] = []
        self.ops: list[dict] = []  # operaciones B12H: writer externo y sus COMMITs

    def enter(self, kind: str, name: str) -> None:
        if not self.stack:
            self.ops.append({"op": name, "commits": []})
        self.stack.append((kind, name))

    def record(self, pending: int) -> None:
        if not pending:
            return
        business = next((n for k, n in reversed(self.stack) if k == "business"), None)
        system = self.stack[-1][1] if self.stack and self.stack[-1][0] == "system" else None
        entry = {"mutating_statements": pending, "committing_writer": business, "nested_system_task": system}
        self.commits.append({"commit_seq": len(self.commits) + 1, **entry})
        if self.ops:
            self.ops[-1]["commits"].append({"commit_seq": len(self.ops[-1]["commits"]) + 1, **entry})


class _Cursor:
    def __init__(self, conn):
        self.conn = conn
        self.cur = psycopg.ClientCursor(conn.raw)
        self.rowcount = -1
        self.lastrowid = None
        self.description = None
        self._rows: list = []

    def execute(self, sql, params=None):
        from deptit_refactor.b12h.audit_actor import is_mutating
        q, p = self.conn.prepare(str(sql), params)
        if is_mutating(sql):
            self.conn.pending += 1
        self.conn.begin()
        self.cur.execute(q, p)
        self.rowcount = self.cur.rowcount
        self.description = self.cur.description
        self._rows = self.cur.fetchall() if self.cur.description else []
        if str(sql).lstrip().upper().startswith("INSERT") and self._rows:
            self.lastrowid = self._rows[0][0]

    def fetchone(self):
        return self._rows.pop(0) if self._rows else None

    def fetchall(self):
        rows, self._rows = self._rows, []
        return rows

    def close(self):
        pass


class _Conn:
    """Conexion certificada: ``tenant`` (get_conn + inyector) o ``raw`` (_pg_raw_conn).  commit = RELEASE."""

    def __init__(self, raw, frames: _Frames, scope=None, injector=None):
        self.raw, self.frames, self.scope, self.injector = raw, frames, scope, injector
        self.pending = 0
        self._sp = None

    def prepare(self, sql, params):
        if self.injector is None:
            return sql, list(params or [])
        inj, head = self.injector, sql.lstrip().upper()
        if head.startswith("SELECT") or head.startswith("WITH"):
            return inj["_pg_scope_select"](sql, params, self.scope)
        if head.startswith("INSERT"):
            return inj["_pg_scope_insert"](sql, params, self.scope)
        if head.startswith("UPDATE") or head.startswith("DELETE"):
            return inj["_pg_scope_update_delete"](sql, params, self.scope)
        return inj["_pg_convert_sql"](sql), list(params or [])

    def begin(self):
        if self._sp is None:
            self._sp = f"cert_des_{next(_SP)}"
            self.raw.execute(f"SAVEPOINT {self._sp}")

    def cursor(self):
        return _Cursor(self)

    def commit(self):
        self.frames.record(self.pending)
        self.pending = 0
        if self._sp is not None:
            self.raw.execute(f"RELEASE SAVEPOINT {self._sp}")
            self._sp = None

    def rollback(self):
        self.pending = 0
        if self._sp is not None:
            self.raw.execute(f"ROLLBACK TO SAVEPOINT {self._sp}")
            self.raw.execute(f"RELEASE SAVEPOINT {self._sp}")
            self._sp = None

    def close(self):
        self.rollback()


def _def_at(name: str, line: int) -> ast.FunctionDef:
    for node in _tree(ENTRY).body:
        if isinstance(node, ast.FunctionDef) and node.name == name and node.lineno == line:
            node.decorator_list = []
            return node
    raise KeyError(f"{name}@{line}")


def _assign_at(name: str, line: int) -> ast.Assign:
    for node in _tree(ENTRY).body:
        if isinstance(node, ast.Assign) and node.lineno == line and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id == name:
            return node
    raise KeyError(f"{name}@{line}")


def _first_def(name: str) -> ast.FunctionDef:
    for node in _tree(ENTRY).body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            node.decorator_list = []
            return node
    raise KeyError(name)


# Orden de ejecucion = orden del entry (cada "pre" se enlaza antes de la redefinicion que lo usa).
SEQUENCE = [
    ("def", "safe_date", None), ("def", "limpiar_texto_tabla", None), ("def", "limpiar_cuil", None),
    ("def", "_clave_cuil", None), ("def", "normalizar_clave", None), ("def", "nombre_completo", None),
    ("def", "horas_segun_dedicacion", None), ("def", "add_column_if_not_exists", None),
    ("def", "_hora_numero", None), ("def", "_fecha_a_timestamp_seguro", None),
    ("def", "registrar_movimiento", None), ("def", "get_periodos", 4713), ("def", "get_docentes", 4462),
    ("def", "docente_existe", None), ("def", "existe_designacion_duplicada", None),
    ("def", "_periodo_id_designacion_departamento_actual", None),
    ("def", "guardar_designacion", 8492), ("def", "actualizar_designacion", 8545),
    ("def", "_tipo_movimiento_designacion_normalizado", None), ("def", "_es_movimiento_vinculado_designacion", None),
    ("def", "_claves_designacion_movimiento", None), ("def", "_ids_movimientos_que_referencian_designacion_conn", None),
    ("def", "_diagnosticar_movimientos_designacion_huerfanos_conn", None), ("def", "eliminar_designacion", None),
    ("def", "eliminar_designaciones_por_error_masivo", None), ("def", "actualizar_designacion_por_error", 9273),
    ("def", "detalle_designacion", None), ("def", "leer_tabla_pegada", None),
    ("def", "normalizar_columna_generica", None), ("def", "normalizar_columnas_designaciones_pegadas", None),
    ("def", "normalizar_fecha_texto", None), ("def", "parsear_designaciones_pegadas", None),
    ("def", "generar_excel_modelo_carga_rapida_designaciones", 16894),
    ("def", "_fecha_iso_integral", None), ("def", "_periodos_ordenados_fechas_v230", None),
    ("def", "_aplicar_periodo_estado_automaticos_v230", None),
    ("def", "get_periodo_por_nombre", None), ("def", "detectar_designaciones_duplicadas_carga", None),
    ("def", "_clave_designacion_desde_row_designacion", None),
    ("def", "_cargo_mas_alto", None), ("def", "_extraer_departamento_origen_prestado", None),
    ("def", "_buscar_departamento_id_por_nombre", None), ("def", "obtener_cargo_prioritario_docente_periodo", 29319),
    ("def", "sincronizar_cargos_asignaciones_docente_periodo", None),
    ("def", "_condicion_periodo_equivalente_sql", None), ("def", "_normalizar_cargo_para_jerarquia", None),
    ("def", "get_designaciones", 32479),
    ("assign", "_guardar_designacion_base_v95", 32500), ("def", "guardar_designacion", 32501),
    ("assign", "_actualizar_designacion_base_v95", 32545), ("def", "actualizar_designacion", 32546),
    ("def", "_finalizar_comisiones_si_sin_designacion_docente_v214", None),
    ("def", "finalizar_designacion_anticipadamente", None),
    ("assign", "_actualizar_designacion_por_error_base_v95", 32811), ("def", "actualizar_designacion_por_error", 32812),
    ("def", "_fecha_iso_correccion_directa_v171", None), ("def", "actualizar_resolucion_fechas_designacion_directo_v171", None),
    ("def", "sincronizar_movimiento_baja_designacion_v207", None),
    ("def", "_estado_designacion_visible_v162", None), ("def", "_es_funcion_no_docente_v162", None),
    ("def", "_texto_funcion_no_docente_limpio_v164", None),
    ("assign", "_get_designaciones_pre_v162", 34440), ("def", "get_designaciones", 34443),
    ("assign", "_guardar_designacion_pre_v162", 34481), ("def", "guardar_designacion", 34484),
    ("assign", "_actualizar_designacion_pre_v162", 34572), ("def", "actualizar_designacion", 34575),
    ("assign", "_actualizar_designacion_por_error_pre_v162", 34610), ("def", "actualizar_designacion_por_error", 34613),
    ("def", "_info_periodo_analisis_v169", None), ("def", "_fecha_fin_designacion_analisis_v169", None),
    ("def", "_periodo_contexto_info_v182", None), ("def", "es_periodo_historico_contexto_v182", None),
    ("def", "_filtrar_foto_designaciones_v169", 39792),
    ("def", "_generar_excel_designaciones_pre_v230", None),
    ("def", "_ordenar_hoja_periodos_excel_v230", None), ("def", "_formula_periodo_excel_v230", None),
    ("def", "_quitar_validaciones_formula_v230", None), ("def", "generar_excel_modelo_carga_rapida_designaciones", 45867),
    ("def", "_mapa_cargos_prioritarios_v200", None),
    ("assign", "_obtener_cargo_prioritario_pre_v200", 46509), ("def", "obtener_cargo_prioritario_docente_periodo", 46666),
    ("def", "_estado_designacion_segun_vigencia_v237", 49656), ("def", "_inferir_periodo_estado_fechas_v230", 49681),
    ("def", "_limpiar_metadatos_finalizacion_si_reactivada_v233", None),
    ("assign", "_actualizar_designacion_pre_v233", 52506), ("assign", "_actualizar_designacion_por_error_pre_v233", 52507),
    ("def", "actualizar_designacion", 52730), ("def", "actualizar_designacion_por_error", 52768),
    ("def", "_etiqueta_acto_v263", None), ("def", "_id_documento_valido_v266", None), ("def", "_usuario_acto_v266", None),
    ("def", "_mapa_actos_designaciones_v266", None), ("def", "_mapa_actos_movimientos_v266", None),
    ("def", "vincular_acto_designacion_v266", None), ("def", "vincular_acto_movimiento_v266", None),
    ("def", "vincular_acto_designaciones_masivo_v267", None), ("def", "desvincular_acto_designaciones_masivo_v267", None),
    ("def", "vincular_acto_movimientos_masivo_v267", None), ("def", "desvincular_acto_movimientos_masivo_v267", None),
    ("def", "_enriquecer_designaciones_acto_v266", None),
    ("assign", "_get_designaciones_pre_v266", 55186), ("def", "get_designaciones", 55187),
    ("def", "_renovacion_concursada_legacy_valida_v268", None), ("def", "_periodos_contexto_v269", None),
    ("def", "_fecha_fin_real_designacion_v269", None), ("def", "_vigente_al_cierre_v269", None),
    ("def", "_firma_designacion_v269", None), ("def", "_detalle_coincide_designacion_v269", None),
    ("def", "_firma_baja_movimiento_v269", None), ("def", "_baja_sin_cambio_real_v269", None),
    ("def", "_depurar_bajas_movimientos_v269", None), ("def", "_canonizar_movimientos_designaciones_v269", None),
    ("def", "get_movimientos_designaciones_periodo_v266", None),
]


def _nodes() -> list:
    nodes = []
    for kind, name, line in SEQUENCE:
        if kind == "assign":
            nodes.append(_assign_at(name, line))
        elif name == "_generar_excel_designaciones_pre_v230":
            nodes.append(_assign_at(name, 45821))
        elif line is None:
            nodes.append(_first_def(name))
        else:
            nodes.append(_def_at(name, line))
    return nodes


def certified_designaciones(raw_conn, institution_id: int, department_id: int, email: str = USER_EMAIL) -> dict:
    """Namespace con las lecturas y writers certificados de Designaciones sobre ``raw_conn`` y el scope indicado."""
    injector = planes_injector()
    frames = _Frames()
    scope = {"kind": "tenant", "institucion_id": int(institution_id), "departamento_id": int(department_id)}

    def get_conn():
        return _Conn(raw_conn, frames, scope, injector)

    def _pg_raw_conn():
        return _Conn(raw_conn, frames)

    def _pg_read_dataframe(sql, params=None):
        cur = psycopg.ClientCursor(raw_conn)
        cur.execute(sql, list(params or []))
        rows = cur.fetchall() if cur.description else []
        cols = [d.name for d in cur.description] if cur.description else []
        return pd.DataFrame(rows, columns=cols)

    def _row_dict(sql):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(sql)
        row = cur.fetchone()
        names = [d.name for d in cur.description] if cur.description else []
        conn.close()
        return None if row is None else dict(zip(names, row))

    abierto_sql = sql_constants(ENTRY, "get_periodo_abierto")[0]
    ultimo_sql = sql_constants(READONLY_QUERIES, "get_ultimo_periodo")[0]
    _St.warnings = []
    from deptit_refactor.catalogs.designaciones import (
        CARGOS, DEDICACIONES, ORDEN_JERARQUICO_CARGOS_COMISION, TIPOS_DESIGNACION,
    )
    from deptit_refactor.catalogs.movimientos import (
        _TIPOS_BAJA_REAL_DESIGNACION_V269, _TIPOS_INICIO_DESIGNACION_V269, MOVIMIENTOS_ACTO_ADMINISTRATIVO_V266,
        TIPOS_MOVIMIENTO_VINCULADOS_DESIGNACION,
    )
    ns = {
        "USE_POSTGRESQL": True, "DATABASE_URL": "postgresql://test", "get_conn": get_conn, "_pg_raw_conn": _pg_raw_conn,
        "pd": pd, "re": re, "json": json, "date": _FixedDate, "datetime": _FixedDateTime, "BytesIO": BytesIO, "st": _St,
        "_pg_current_inst_id": lambda: institution_id, "_pg_current_dep_id": lambda: department_id,
        "_pg_read_dataframe": _pg_read_dataframe,
        "invalidar_cache_rendimiento_v191": lambda *_: None, "limpiar_cache_comisiones_operativas": lambda *_: None,
        "asegurar_esquema_actos_administrativos_v266": lambda: None,
        "sincronizar_vencimientos_concursados_v268": lambda *_: 0,  # B12F: reconciliacion omitida al leer
        "get_periodo_abierto": lambda: _row_dict(abierto_sql), "get_ultimo_periodo": lambda: _row_dict(ultimo_sql),
        "current_user": lambda: {"email": email},
        "_version_dependencias_v200": lambda *a, **k: 0,
        "CARGOS": CARGOS, "DEDICACIONES": DEDICACIONES, "TIPOS_DESIGNACION": TIPOS_DESIGNACION,
        "ORDEN_JERARQUICO_CARGOS_COMISION": ORDEN_JERARQUICO_CARGOS_COMISION,
        "ESTADOS_DESIGNACION": ["Activa", "Finalizada", "Suspendida"], "HORAS_OPCIONES": [10, 20, 30, 40, 50],
        "MOVIMIENTOS_ACTO_ADMINISTRATIVO_V266": MOVIMIENTOS_ACTO_ADMINISTRATIVO_V266,
        "TIPOS_MOVIMIENTO_VINCULADOS_DESIGNACION": TIPOS_MOVIMIENTO_VINCULADOS_DESIGNACION,
        "_TIPOS_INICIO_DESIGNACION_V269": _TIPOS_INICIO_DESIGNACION_V269,
        "_TIPOS_BAJA_REAL_DESIGNACION_V269": _TIPOS_BAJA_REAL_DESIGNACION_V269,
        "_departamento_actual_operativo_nombre": lambda: "",
    }
    ns["TIPOS_MOVIMIENTO_DOCENTE_POR_ERROR"] = ast.literal_eval(_top_assign("TIPOS_MOVIMIENTO_DOCENTE_POR_ERROR").value)
    exec(compile(ast.Module(body=_nodes(), type_ignores=[]), str(ENTRY), "exec"), ns)
    # La cache v200 (lru_cache) queda sin decorador: B12I la saltea dentro de un writer (lectura fresca).
    for name in BUSINESS + SYSTEM:
        kind = "system" if name in SYSTEM else "business"

        def framed(*args, _fn=ns[name], _name=name, _kind=kind, **kwargs):
            frames.enter(_kind, _name)
            try:
                return _fn(*args, **kwargs)
            finally:
                frames.stack.pop()
        ns[name] = framed
    ns["_frames"] = frames
    return ns


_ANIO_PRIMERO = re.compile(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?:[ T].*)?")


def corregir_fecha_anio_primero(ns: dict) -> dict:
    """DESVIACION DELIBERADA Y DOCUMENTADA (docs/ETAPA5_FINAL_REMEDIATION.md).  El ``normalizar_fecha_texto``
    certificado invierte dia y mes en las fechas año-primero con dia <= 12 (2026-03-01 -> 2026-01-03); NEXT lo
    corrige.  Solo para los diferenciales de Carga rapida: reemplaza en el namespace certificado UNICAMENTE esa
    funcion por un oraculo independiente (``datetime.date``, no el codigo de NEXT) que corrige el formato año-primero
    y delega todo lo demas en la funcion certificada.  El resto del parser y de los writers sigue siendo certificado."""
    certificada = ns["normalizar_fecha_texto"]

    def normalizar_fecha_texto(valor, fallback=""):
        txt = ns["limpiar_texto_tabla"](valor)
        m = _ANIO_PRIMERO.fullmatch(txt) if txt else None
        if m is None:
            return certificada(valor, fallback)
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except ValueError:
            return txt

    ns["normalizar_fecha_texto"] = normalizar_fecha_texto
    return ns


# ------------------------------------------------------------------------------------------ estado comparable
def state(conn, inst: int, dep: int, max_mov: int) -> dict:
    """Designaciones del departamento (sin id; ids nuevos normalizados), movimientos nuevos, asignaciones y vinculos."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM designaciones WHERE institucion_id=%s AND departamento_id=%s ORDER BY id",
                    [inst, dep])
        des = list(cur.fetchall())
        cur.execute("SELECT periodo_id, fecha, tipo_movimiento, cuil, nombre, detalle, observaciones, horas_variacion, "
                    "institucion_id, departamento_id FROM movimientos WHERE id > %s ORDER BY id", [max_mov])
        movs = list(cur.fetchall())
        cur.execute("SELECT count(*) AS n, coalesce(sum(id),0) AS s FROM movimientos WHERE id <= %s", [max_mov])
        movs_viejos = cur.fetchone()
        cur.execute("SELECT id, rol, estado, observaciones FROM asignaciones_docentes_comision WHERE institucion_id=%s "
                    "ORDER BY id", [inst])
        asig = list(cur.fetchall())
        cur.execute("SELECT documento_id, designacion_id FROM documentos_respaldo_designaciones ORDER BY designacion_id")
        links_d = list(cur.fetchall())
        cur.execute("SELECT documento_id, movimiento_id FROM documentos_respaldo_movimientos ORDER BY movimiento_id")
        links_m = list(cur.fetchall())
    viejos = {r["id"] for r in des if r["id"] <= MAX_DES_ID[0]}

    def norm(r):
        d = {k: v for k, v in r.items() if k != "id"}
        d["_id"] = r["id"] if r["id"] in viejos else "nuevo"
        return json.dumps(d, sort_keys=True, default=str)

    return {"designaciones": sorted(norm(r) for r in des),
            "movimientos": [json.dumps(m, sort_keys=True, default=str) for m in movs],
            "movimientos_viejos": dict(movs_viejos), "asignaciones": asig,
            "links_designaciones": [(r["documento_id"], r["designacion_id"] if r["designacion_id"] in viejos else "nuevo")
                                    for r in links_d],
            "links_movimientos": [(r["documento_id"], r["movimiento_id"] if r["movimiento_id"] <= max_mov else "nuevo")
                                  for r in links_m]}


MAX_DES_ID = [0]


def baseline(conn) -> int:
    MAX_DES_ID[0] = conn.execute("SELECT coalesce(max(id),0) FROM designaciones").fetchone()[0]
    return conn.execute("SELECT coalesce(max(id),0) FROM movimientos").fetchone()[0]


def audit_rows(conn) -> list[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM b12h_audit_log WHERE occurred_at >= transaction_timestamp() "
                    "ORDER BY occurred_at, correlation_id, event_seq")
        return list(cur.fetchall())


def free_cuil(conn, base: str) -> str:
    digits = re.sub(r"\D", "", base)
    for table in ("docentes", "designaciones", "movimientos", "asignaciones_docentes_comision"):
        n = conn.execute(f"SELECT count(*) FROM {table} WHERE regexp_replace(COALESCE(cuil,''),'[^0-9]','','g')=%s",
                         [digits]).fetchone()[0]
        assert n == 0, f"el CUIL sintetico {base} ya existe en {table}"
    return base


# ------------------------------------------------------------------------------------------ fixtures de servicio
def make_designaciones(service, audit_store, db_conn, **kwargs):
    from designaciones.service import DesignacionesService

    kwargs.setdefault("transaction", lambda: savepoint(db_conn))
    return DesignacionesService(None, service, audit_store, today=lambda: FIXED_TODAY, now=lambda: FIXED_NOW, **kwargs)


@pytest.fixture
def designaciones(service, repo, db_conn, audit_store):
    repo.departments_rows.extend(dict(d) for d in EXTRA_DEPARTMENTS)
    return make_designaciones(service, audit_store, db_conn)


@pytest.fixture
def http(service, designaciones):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from auth.routes import router as auth_router
    from designaciones.routes import router as designaciones_router

    application = FastAPI()
    application.include_router(auth_router)
    application.include_router(designaciones_router)
    application.state.auth = service
    application.state.designaciones = designaciones
    return TestClient(application, base_url="http://localhost")
