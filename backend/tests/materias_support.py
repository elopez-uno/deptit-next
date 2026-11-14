"""Soporte de los tests de Materias.

- Conexion real que nunca confirma (``db_conn``), SAVEPOINT por unidad de trabajo y auditoria falsa (periodos_support).
- ``certified_materias``: funciones del entry certificado (AST, sin modificar reference_fix02) ejecutadas sobre la base
  real con la conexion certificada ``get_planes_conn()`` (kind "planes"): inyector v193 + B12J instalado sin cambios,
  y ``_pg_raw_conn()`` para las guardas de Comisiones.  Sus COMMIT son RELEASE SAVEPOINT dentro del test.
- ``state``: foto comparable de las 4 tablas de la fuente unica de planes de una institucion (ids reemplazados por
  claves naturales para comparar altas hechas con secuencias distintas).
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime
from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest
from psycopg.rows import dict_row

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

from docentes_support import RawConnection, _StStub, _top_assign, exec_entry  # noqa: E402
from periodos_support import (  # noqa: E402,F401  (fixtures re-exportados)
    ENTRY, EXTRA_DEPARTMENTS, FIXED_TODAY, FakeAuditStore, _FixedDate, audit_store, certified_injector, db_conn,
    entry_defs, savepoint, session_for,
)

FIXED_NOW = datetime(2026, 10, 26, 11, 0, 0)


class _FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return FIXED_NOW


def planes_injector() -> dict:
    """Inyector efectivo del entry para SELECT: ``_pg_scope_select`` v193 (l. 42898) re-enlazado por B12J."""
    from deptit_refactor.b12j.left_join_scope import install_left_join_scope

    ns = certified_injector()
    exec_entry([("_pg_scope_select", 1)], ns)
    install_left_join_scope(ns)
    return ns


class PlanesCursor:
    def __init__(self, conn):
        self.conn = conn
        self.cur = conn.raw.cursor()
        self.rowcount = -1
        self.lastrowid = None
        self.description = None
        self._rows: list = []

    def execute(self, sql, params=None):
        inj, scope = self.conn.injector, self.conn.scope
        head = str(sql).lstrip().upper()
        if head.startswith("SELECT") or head.startswith("WITH"):
            q, p = inj["_pg_scope_select"](str(sql), params, scope)
        elif head.startswith("INSERT"):
            q, p = inj["_pg_scope_insert"](sql, params, scope)
        elif head.startswith("UPDATE") or head.startswith("DELETE"):
            q, p = inj["_pg_scope_update_delete"](sql, params, scope)
        else:
            q, p = inj["_pg_convert_sql"](sql), list(params or [])
        from deptit_refactor.b12h.audit_actor import is_mutating
        if is_mutating(sql):
            self.conn.pending += 1
        self.conn.begin()
        self.cur.execute(q, p)
        self.rowcount = self.cur.rowcount
        self.description = self.cur.description
        self._rows = self.cur.fetchall() if self.cur.description else []
        if head.startswith("INSERT") and self._rows:
            self.lastrowid = self._rows[0][0]

    def fetchone(self):
        return self._rows.pop(0) if self._rows else None

    def fetchall(self):
        rows, self._rows = self._rows, []
        return rows

    def close(self):
        pass


class PlanesConnection:
    _n = 0

    def __init__(self, raw, injector, institution_id, commits, stack):
        self.raw, self.injector = raw, injector
        self.scope = {"kind": "planes", "institucion_id": int(institution_id)}
        self.pending = 0
        self._commits, self._stack = commits, stack
        self._savepoint = None

    def begin(self):
        if self._savepoint is None:
            PlanesConnection._n += 1
            self._savepoint = f"planes_cert_{PlanesConnection._n}"
            self.raw.execute(f"SAVEPOINT {self._savepoint}")

    def _end(self, commit):
        if self._savepoint is not None:
            if not commit:
                self.raw.execute(f"ROLLBACK TO SAVEPOINT {self._savepoint}")
            self.raw.execute(f"RELEASE SAVEPOINT {self._savepoint}")
            self._savepoint = None

    def cursor(self):
        return PlanesCursor(self)

    def commit(self):
        if self.pending:
            self._commits.append({"commit_seq": len(self._commits) + 1, "mutating_statements": self.pending,
                                  "committing_writer": self._stack[-1] if self._stack else None})
        self.pending = 0
        self._end(True)

    def rollback(self):
        self.pending = 0
        self._end(False)

    def close(self):
        self.rollback()


class _St(_StStub):
    warnings: list = []

    @staticmethod
    def warning(msg, *a, **k):
        _St.warnings.append(msg)


CERT_FUNCS = [
    "normalizar_clave", "limpiar_texto_tabla", "normalizar_codigo_materia", "_valor_limpio_materia", "safe_index",
    "get_facultades_escuelas_disponibles", "escuela_para_filtro", "get_carreras", "get_carrera",
    "existe_carrera_duplicada", "guardar_carrera", "actualizar_carrera", "eliminar_carrera", "get_opciones_carreras",
    "get_plan_estudio", "get_plan_estudio_todas", "_asegurar_columnas_materias", "_filtrar_materias_dataframe",
    "_filtrar_busqueda_materias", "_opciones_carrera_plan_desde_materias", "filtrar_dataframe_por_texto",
    "get_materias_totales", "get_materias_unicas", "guardar_materia", "actualizar_materia",
    "actualizar_codigo_nombre_materias_desde_plan", "_ids_materias_referenciadas_por_comisiones",
    "limpiar_registros_materias_fuera_del_plan", "quitar_materia_del_plan", "eliminar_materia",
    "normalizar_columnas_plan_pegado", "parsear_plan_pegado", "existe_materia_duplicada",
    "obtener_conflictos_codigo_materia", "validar_codigo_materia_institucional",
    "detectar_conflictos_codigo_en_tabla", "detectar_conflictos_codigo_con_base", "detectar_materias_duplicadas_plan",
    "es_materia_optativa_electiva", "tipo_espacio_curricular_v120", "get_espacios_optativos_electivos_v120",
    "get_opcion_curricular_v120", "_get_vinculos_opciones_lote_v127", "_get_vinculos_opcion_curricular_v120_no_cache_v127",
    "_get_opciones_curriculares_v120_no_cache_v127", "_normalizar_tipo_opcion_v120",
    "existe_opcion_curricular_duplicada_v120", "validar_cambio_tipo_espacio_opcion_v120",
    "guardar_opcion_curricular_v120", "actualizar_opcion_curricular_v120", "agregar_vinculos_opcion_curricular_v120",
    "_etiqueta_espacio_plan_opcion_v124", "_catalogo_espacios_plan_opcion_v124",
    ("generar_excel_modelo_carga_rapida_opciones_v124", 0), "_normalizar_encabezado_opcion_v124",
    "leer_excel_carga_rapida_opciones_v124", "_buscar_opcion_equivalente_v124",
    "cargar_opciones_curriculares_excel_v124", "quitar_vinculo_opcion_curricular_v120",
    "_contar_comisiones_opcion_curricular_v120", "eliminar_opcion_curricular_v120", "_deptit_join_unicos",
    "_normalizar_modo_comparticion_v137", "_clave_materia_unica_codigo_nombre", "_clave_materia_conceptual_v137",
    "_etiqueta_plan_materia_v137", "_ids_grupo_comparticion_materia_v137", "get_apariciones_misma_identidad_v137",
    "guardar_configuracion_comparticion_materia_v137",
]
WRITERS = ["guardar_carrera", "actualizar_carrera", "eliminar_carrera", "guardar_materia", "actualizar_materia",
           "actualizar_codigo_nombre_materias_desde_plan", "guardar_configuracion_comparticion_materia_v137",
           "quitar_materia_del_plan", "eliminar_materia", "limpiar_registros_materias_fuera_del_plan",
           "guardar_opcion_curricular_v120", "actualizar_opcion_curricular_v120", "eliminar_opcion_curricular_v120",
           "agregar_vinculos_opcion_curricular_v120", "quitar_vinculo_opcion_curricular_v120",
           "cargar_opciones_curriculares_excel_v124"]


def certified_materias(raw_conn, institution_id: int) -> dict:
    injector = planes_injector()
    # B12B: institucion de la sesion; el departamento no interviene en las tablas institucionales de la fuente de planes.
    injector["_pg_current_inst_id"] = lambda: institution_id
    injector["_pg_current_dep_id"] = lambda: None
    commits: list[dict] = []
    stack: list[str] = []

    def get_planes_conn():
        return PlanesConnection(raw_conn, injector, institution_id, commits, stack)

    def _pg_raw_conn():
        return RawConnection(raw_conn, commits, stack)

    def _pg_read_dataframe(sql, params=None):
        with raw_conn.cursor() as cur:
            cur.execute(sql, list(params or []))
            rows = cur.fetchall() if cur.description else []
            cols = [d.name for d in cur.description] if cur.description else []
        return pd.DataFrame(rows, columns=cols)

    ns = {
        "USE_POSTGRESQL": True, "MODO_SANEAMIENTO_MATERIAS_INDIVIDUAL": False, "get_planes_conn": get_planes_conn,
        "_pg_raw_conn": _pg_raw_conn, "_pg_read_dataframe": _pg_read_dataframe,
        "_pg_current_inst_id": lambda: institution_id, "pd": pd, "re": re, "json": json, "hashlib": hashlib,
        "date": _FixedDate, "datetime": _FixedDateTime, "BytesIO": BytesIO, "st": _St,
        "sincronizar_planes_si_corresponde": lambda: None, "limpiar_cache_comisiones_operativas": lambda *_: None,
    }
    from deptit_refactor.catalogs.materias import (ETIQUETAS_COMPARTICION_MATERIA, MODO_COMPARTICION_AUTO,
                                                   MODO_COMPARTICION_ESPECIFICA, MODO_COMPARTICION_SELECCIONADA,
                                                   TIPOS_OPCION_CURRICULAR)
    ns.update(ETIQUETAS_COMPARTICION_MATERIA=ETIQUETAS_COMPARTICION_MATERIA, MODO_COMPARTICION_AUTO=MODO_COMPARTICION_AUTO,
              MODO_COMPARTICION_ESPECIFICA=MODO_COMPARTICION_ESPECIFICA,
              MODO_COMPARTICION_SELECCIONADA=MODO_COMPARTICION_SELECCIONADA, TIPOS_OPCION_CURRICULAR=TIPOS_OPCION_CURRICULAR)
    picks = [(f, 0) if isinstance(f, str) else f for f in CERT_FUNCS]
    exec_entry(picks, ns, assigns=("ANIOS", "CUATRIMESTRES_MAT", "DURACIONES", "DICTADOS", "ESTADOS_CARRERA",
                                   "ESTADOS_MATERIA", "ESTADOS_OPCION_CURRICULAR"))
    # Lecturas sin cache v127 (dentro del writer B12I lee fresco; fuera, la cache no cambia el resultado).
    ns["get_vinculos_opcion_curricular_v120"] = lambda oid, solo_vigentes=False: \
        ns["_get_vinculos_opcion_curricular_v120_no_cache_v127"](oid, solo_vigentes=solo_vigentes)
    ns["get_opciones_curriculares_v120"] = lambda tipo=None, estado=None: \
        ns["_get_opciones_curriculares_v120_no_cache_v127"](tipo=tipo, estado=estado)
    for name in WRITERS:
        def framed(*args, _fn=ns[name], _name=name, **kwargs):
            stack.append(_name)
            try:
                return _fn(*args, **kwargs)
            finally:
                stack.pop()
        ns[name] = framed
    ns["_commits"] = commits
    return ns


# ------------------------------------------------------------------------------------------ estado comparable
def state(conn, inst: int) -> dict:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM carreras WHERE institucion_id = %s", [inst])
        carreras = list(cur.fetchall())
        cur.execute("SELECT * FROM materias WHERE institucion_id = %s", [inst])
        materias = list(cur.fetchall())
        cur.execute("SELECT * FROM opciones_curriculares WHERE institucion_id = %s", [inst])
        opciones = list(cur.fetchall())
        cur.execute("SELECT * FROM opcion_curricular_materias WHERE institucion_id = %s", [inst])
        vinculos = list(cur.fetchall())
    ck = {r["id"]: f"{r['escuela']}|{r['nombre']}|{r['plan_version']}" for r in carreras}
    mk = {r["id"]: f"{ck.get(r['carrera_id'])}|{r['codigo']}|{r['asignatura']}|{r['anio']}|{r['en_plan']}"
          for r in materias}
    ok = {r["id"]: f"{r['tipo']}|{r['codigo']}|{r['nombre']}|{r['escuela_oferente']}" for r in opciones}

    def dump(rows, drop, mapping):
        out = []
        for r in rows:
            d = {k: v for k, v in r.items() if k not in drop}
            for col, m in mapping.items():
                if col in d:
                    d[col] = m.get(d[col], d[col])
            out.append(json.dumps(d, sort_keys=True, default=str))
        return sorted(out)

    return {"carreras": dump(carreras, {"id"}, {}),
            "materias": dump(materias, {"id"}, {"carrera_id": ck}),
            "opciones": dump(opciones, {"id"}, {}),
            "vinculos": dump(vinculos, {"id"}, {"materia_id": mk, "opcion_id": ok})}


# ------------------------------------------------------------------------------- segunda institucion sintetica
UBA = 2  # institucion real sin estructura academica (datos de prueba eliminados el 2026-10-26)


@pytest.fixture
def uba_sintetica(db_conn) -> dict:
    """Estructura academica sintetica de UBA dentro de la transaccion del test (nunca se confirma: db_conn hace
    ROLLBACK). Reemplaza la dependencia de datos reales de UBA para las pruebas de aislamiento entre instituciones;
    incluye un homonimo de una carrera de UNO (Abogacia) y una materia fuera del plan."""
    q = lambda sql, p: db_conn.execute(sql, p).fetchone()[0]  # noqa: E731
    carreras = [q("INSERT INTO carreras (institucion_id, escuela, nombre, codigo, titulo_otorga, plan_version, duracion, "
                  "estado, observaciones) VALUES (%s, %s, %s, %s, '', 'Plan vigente', '', %s, '') RETURNING id",
                  [UBA, esc, nombre, cod, estado])
                for esc, nombre, cod, estado in [("ZZUBA Escuela de Derecho", "Abogacía", "ZZD1", "Activa"),
                                                 ("ZZUBA Escuela de Derecho", "ZZUBA Traductorado", "ZZD2", "Activa"),
                                                 ("ZZUBA Escuela de Ciencias", "ZZUBA Física", "ZZC1", "Inactiva")]]
    materias = []
    for i, (cid, anio, en_plan) in enumerate([(carreras[0], "1° Año", 1), (carreras[0], "2° Año", 1),
                                              (carreras[0], "1° Año", 0), (carreras[1], "1° Año", 1),
                                              (carreras[2], "1° Año", 1)]):
        materias.append(q(
            "INSERT INTO materias (institucion_id, carrera_id, codigo, asignatura, carrera, escuela, anio, dictado, "
            "carga_semanal, carga_total, cuatrimestre, duracion, plan_version, orden, estado, observaciones, en_plan) "
            "SELECT %s, c.id, %s, %s, c.nombre, c.escuela, %s, 'Presencial', 4, 64, '1', 'Cuatrimestral', "
            "c.plan_version, %s, 'Activa', '', %s FROM carreras c WHERE c.id = %s RETURNING id",
            [UBA, f"ZZU{i}", f"ZZUBA Materia {i}", anio, i, en_plan, cid]))
    opcion = q("INSERT INTO opciones_curriculares (institucion_id, tipo, codigo, nombre, escuela_oferente, estado, "
               "observaciones, fecha_creacion, fecha_actualizacion) VALUES (%s, 'Optativa', 'ZZOPT', 'ZZUBA Optativa', "
               "'ZZUBA Escuela de Derecho', 'Activa', '', '2026-10-26 11:00:00', '2026-10-26 11:00:00') RETURNING id",
               [UBA])
    vinculo = q("INSERT INTO opcion_curricular_materias (institucion_id, opcion_id, materia_id, fecha_vinculacion) "
                "VALUES (%s, %s, %s, '2026-10-26 11:00:00') RETURNING id", [UBA, opcion, materias[1]])
    return {"carreras": carreras, "materias": materias, "opcion": opcion, "vinculo": vinculo}


def audit_rows(conn) -> list[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM b12h_audit_log WHERE occurred_at >= transaction_timestamp() "
                    "ORDER BY occurred_at, correlation_id, event_seq")
        return list(cur.fetchall())


# ------------------------------------------------------------------------------------------ fixtures
def make_materias(service, audit_store, db_conn, **kwargs):
    from materias.service import MateriasService

    kwargs.setdefault("transaction", lambda: savepoint(db_conn))
    return MateriasService(None, service, audit_store, today=lambda: FIXED_TODAY, now=lambda: FIXED_NOW, **kwargs)


@pytest.fixture
def materias(service, repo, db_conn, audit_store):
    repo.departments_rows.extend(dict(d) for d in EXTRA_DEPARTMENTS)
    return make_materias(service, audit_store, db_conn)


@pytest.fixture
def http(service, materias):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from auth.routes import router as auth_router
    from materias.routes import router as materias_router

    application = FastAPI()
    application.include_router(auth_router)
    application.include_router(materias_router)
    application.state.auth = service
    application.state.materias = materias
    return TestClient(application, base_url="http://localhost")
