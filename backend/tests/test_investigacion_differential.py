"""Diferenciales de LECTURA de Investigacion: funciones certificadas (``certified_investigacion``) vs NEXT (``Lecturas`` /
servicio), sobre ``deptit_next_dev`` real dentro de una transaccion que se revierte.

Cubre: catalogo v199 (todos, vigentes por periodo, sin periodo), ``get_investigacion_docente`` (local, institucional,
con bajas, por CUIL, foto al cierre v183, enriquecimiento v277), periodo actual / historico cerrado / historico ABIERTO
por excepcion, padron v276 (Consolidado v240), capacidad v184 con y sin exclusion, excesos v184, duplicado e
integrantes v217, actos v263 y el Excel integral (byte a byte salvo ``docProps/core.xml``)."""

from __future__ import annotations

import zipfile
from datetime import date
from decimal import Decimal
from io import BytesIO

import pandas as pd
import psycopg
import pytest

from comisiones.service import _jsonable
from investigacion import excel as X
from investigacion.lecturas import Lecturas
from investigacion.repository import InvestigacionRepository
from investigacion_support import (  # noqa: F401  (fixtures)
    FIXED_TODAY, audit_store, certified_investigacion, db_conn, investigacion, lock_conn, session_for,
)

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")

INST = 1


def _norm(v):
    v = _jsonable(v)
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, Decimal):
        return float(v)
    return v


def _rows(df: pd.DataFrame) -> list[dict]:
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return []
    return [{str(k): _norm(v) for k, v in r.items()} for r in df.to_dict(orient="records")]


def igual(a: pd.DataFrame, b: pd.DataFrame, contexto=""):
    ca = list(a.columns) if isinstance(a, pd.DataFrame) else []
    cb = list(b.columns) if isinstance(b, pd.DataFrame) else []
    ra, rb = _rows(a), _rows(b)
    if ra or rb:
        assert ca == cb, f"{contexto}: columnas\ncert {ca}\nnext {cb}"
    assert len(ra) == len(rb), f"{contexto}: {len(ra)} vs {len(rb)} filas"
    for i, (x, y) in enumerate(zip(ra, rb)):
        assert x == y, f"{contexto}: fila {i}\ncert {x}\nnext {y}"


def lecturas(db_conn, dep, rol="usuario_departamento"):
    return Lecturas(InvestigacionRepository(db_conn, INST, dep), FIXED_TODAY, rol)


def _periodos(db_conn, dep):
    return {r[1]: r[0] for r in db_conn.execute(
        "SELECT id, nombre FROM periodos WHERE institucion_id=%s AND departamento_id=%s", [INST, dep]).fetchall()}


@pytest.mark.parametrize("dep", [1, 2, 3])
def test_catalogo_v199(db_conn, dep):
    ns = certified_investigacion(db_conn, INST, dep)
    L = lecturas(db_conn, dep)
    igual(ns["get_proyectos_investigacion"](), L.proyectos(), "catalogo")
    igual(ns["get_proyectos_investigacion"](solo_activos=True), L.proyectos(solo_activos=True), "activos")
    for nombre, pid in _periodos(db_conn, dep).items():
        igual(ns["get_proyectos_investigacion"](solo_activos=True, periodo_id=pid),
              L.proyectos(solo_activos=True, periodo_id=pid), f"vigentes {nombre}")


@pytest.mark.parametrize("dep", [1, 2, 9])
def test_asignaciones_local_e_institucional(db_conn, dep):
    ns = certified_investigacion(db_conn, INST, dep)
    L = lecturas(db_conn, dep)
    g = ns["get_investigacion_docente"]
    for nombre, pid in _periodos(db_conn, dep).items():
        hist = ns["es_periodo_historico_contexto_v182"](pid)
        assert hist == L.es_historico(pid)
        igual(g(periodo_id=pid, incluir_bajas=hist), L.asignaciones(periodo_id=pid, incluir_bajas=hist), f"tab4 {nombre}")
        igual(g(periodo_id=pid), L.asignaciones(periodo_id=pid), f"activas/foto {nombre}")
        igual(g(periodo_id=pid, todos_departamentos=True), L.asignaciones(periodo_id=pid, todos_departamentos=True),
              f"institucional {nombre}")
    igual(g(incluir_bajas=True, todos_departamentos=True), L.asignaciones(incluir_bajas=True, todos_departamentos=True),
          "historial institucional")


def test_foto_al_cierre_y_proyecto_suspendido(db_conn):
    """2026-1 (Cerrado) del dep 1: las 14 activas, el proyecto 8 Suspendido (no vigente) y las bajas 29/30/36/40."""
    ns = certified_investigacion(db_conn, INST, 1)
    L = lecturas(db_conn, 1)
    pid = _periodos(db_conn, 1)["2026-1"]
    assert L.es_historico(pid)
    foto = L.asignaciones(periodo_id=pid)
    igual(ns["get_investigacion_docente"](periodo_id=pid), foto, "foto")
    assert len(foto) == 14
    vig = L.proyectos(solo_activos=True, periodo_id=pid)
    assert 8 not in set(vig["id"].astype(int))  # Suspendido hoy: no figura vigente ni en el historico (D6-8)
    bajas = L.asignaciones(periodo_id=_periodos(db_conn, 1)["2026-2"], incluir_bajas=True)
    assert {29, 30, 36, 40} <= set(bajas["id"].astype(int))


def test_historico_abierto_por_excepcion(db_conn):
    """Abrir 2026-1 por excepcion (dentro de la transaccion revertida): lecturas con foto al cierre y referencia v182."""
    per = _periodos(db_conn, 1)
    with db_conn.transaction():
        db_conn.execute("UPDATE periodos SET estado='Cerrado' WHERE institucion_id=1 AND departamento_id=1")
        db_conn.execute("UPDATE periodos SET estado='Abierto' WHERE id=%s", [per["2026-1"]])
        ns = certified_investigacion(db_conn, INST, 1)
        L = lecturas(db_conn, 1)
        ab = L.periodo_abierto()
        assert ab["id"] == per["2026-1"] and L.es_historico(ab["id"])
        igual(ns["get_proyectos_investigacion"](solo_activos=True, periodo_id=ab["id"]),
              L.proyectos(solo_activos=True, periodo_id=ab["id"]), "vigentes historico")
        igual(ns["get_investigacion_docente"](periodo_id=ab["id"]), L.asignaciones(periodo_id=ab["id"]), "editar/bajas")
        for cuil in L.asignaciones(periodo_id=ab["id"])["cuil"].head(4):
            assert ns["capacidad_proyectos_docente_v184"](cuil, ab["id"]) == L.capacidad(cuil, ab["id"])
        igual(ns["detectar_excesos_proyectos_v184"](ab["id"], "investigacion"), L.detectar_excesos(ab["id"]), "excesos")
        raise psycopg.Rollback()


def test_padron_v276(db_conn):
    ns = certified_investigacion(db_conn, INST, 1)
    L = lecturas(db_conn, 1)
    pid = _periodos(db_conn, 1)["2026-2"]
    cert = ns["_docentes_asignables_proyectos_institucional_pg_v276"](pid)
    nxt = L.padron()
    # Etapa 5 / Tanda C (C1): ``cargo`` / ``cargo_final`` / ``dedicacion`` concatenan (" / ") en el orden de las
    # designaciones del docente; el certificado no desempata por ``d.id`` (orden fisico de las filas), NEXT si.  Se
    # comparan como multiconjunto; todo lo demas, exacto.
    for df in (cert, nxt):
        for col in ("cargo", "cargo_final", "dedicacion"):
            if col in df.columns:
                df[col] = df[col].map(lambda v: " / ".join(sorted(v.split(" / "))) if isinstance(v, str) else v)
    igual(cert, nxt, "padron")
    for k in ("consolidado_docentes_unicos_v276", "selector_docentes_unicos_v276", "diagnostico_v276"):
        assert cert.attrs.get(k) == nxt.attrs.get(k), k
    assert len(nxt) > 0


def test_capacidad_con_y_sin_exclusion(db_conn):
    ns = certified_investigacion(db_conn, INST, 1)
    L = lecturas(db_conn, 1)
    pid = _periodos(db_conn, 1)["2026-2"]
    asig = L.asignaciones(periodo_id=pid)
    assert not asig.empty
    for _, r in asig.iterrows():
        cuil, aid = r["cuil"], int(r["id"])
        assert ns["capacidad_proyectos_docente_v184"](cuil, pid) == L.capacidad(cuil, pid)
        assert ns["capacidad_proyectos_docente_v184"](cuil, pid, excluir_tipo="investigacion", excluir_id=aid) == \
            L.capacidad(cuil, pid, "investigacion", aid)
    igual(ns["detectar_excesos_proyectos_v184"](pid, "investigacion"), L.detectar_excesos(pid), "excesos")
    for cuil in asig["cuil"].head(3):
        igual(ns["_detalle_proyectos_docente_v187"](cuil, pid), L.detalle_proyectos_docente_v187(cuil, pid), "v187")


@pytest.mark.parametrize("dep", [1, 4])
def test_duplicado_e_integrantes_v217(db_conn, dep):
    ns = certified_investigacion(db_conn, INST, dep)
    L = lecturas(db_conn, dep)
    pid = _periodos(db_conn, dep)["2026-2"]
    for proyecto in L.proyectos(solo_activos=True, periodo_id=pid)["id"].head(12):
        integ = L.integrantes(int(proyecto), pid)
        igual(ns["get_integrantes_activos_proyecto_periodo"](int(proyecto), pid), integ, f"integrantes {proyecto}")
        for _, r in integ.head(2).iterrows():
            a = ns["buscar_asignacion_activa_docente_proyecto"](pid, int(proyecto), r["cuil"], todos_departamentos=True)
            b = L.buscar_activa(pid, int(proyecto), r["cuil"])
            assert {k: _norm(v) for k, v in a.items()} == {k: _norm(v) for k, v in b.items()}
            assert L.buscar_activa(pid, int(proyecto), r["cuil"], excluir_id=int(r["id"])) == \
                (ns["buscar_asignacion_activa_docente_proyecto"](pid, int(proyecto), r["cuil"], excluir_id=int(r["id"]),
                                                                   todos_departamentos=True) or {})


def test_actos_v263(db_conn):
    ns = certified_investigacion(db_conn, INST, 1)
    L = lecturas(db_conn, 1)
    ids = L.proyectos()["id"].astype(int).tolist()
    igual(ns["get_documentos_proyectos_v263"]("investigacion", ids), L.documentos_proyectos(ids), "actos")


def _partes(contenido: bytes) -> dict:
    with zipfile.ZipFile(BytesIO(contenido)) as z:
        return {n: z.read(n) for n in sorted(z.namelist()) if n != "docProps/core.xml"}


@pytest.mark.parametrize("dep", [1, 2])
def test_excel_integral_byte_a_byte(db_conn, dep):
    ns = certified_investigacion(db_conn, INST, dep)
    L = lecturas(db_conn, dep)
    pid = _periodos(db_conn, dep)["2026-2"]
    cert = ns["generar_excel_modelo_proyectos_v217"]("investigacion", pid)
    nxt = X.integral_v217(L.proyectos(), L.padron(), L.asignaciones(periodo_id=pid, incluir_bajas=False))
    assert _partes(cert) == _partes(nxt)
    # Sin periodo abierto: hoja de asignaciones vacia.
    assert _partes(ns["generar_excel_modelo_proyectos_v217"]("investigacion", None)) == \
        _partes(X.integral_v217(L.proyectos(), pd.DataFrame(), pd.DataFrame()))
    # Lectura del propio modelo: mismas filas que el lector certificado.
    igual(ns["leer_excel_carga_rapida_proyectos_v127"](nxt), X.leer_carga_rapida_v127(nxt), "leer v127")
    igual(ns["leer_asignaciones_proyectos_excel_v217"](nxt), X.leer_asignaciones_v217(nxt), "leer v217")


def test_datos_legacy_preservados(db_conn):
    """Casos del relevamiento (§12): sin normalizar CUIL con guiones, roles femeninos, 2,5 hs, 0 hs, otro departamento."""
    L = lecturas(db_conn, 1)
    todas = L.asignaciones(incluir_bajas=True, todos_departamentos=True)
    # Etapa 5 / C2: esperado por SQL independiente (antes literales 157 / 153 de la base dev).
    total, activas = db_conn.execute(
        "SELECT count(*), count(*) FILTER (WHERE COALESCE(estado_asignacion, 'Activa') = 'Activa') "
        "FROM investigacion_docente WHERE institucion_id = 1").fetchone()
    assert len(todas) == total and (todas["estado_asignacion"] == "Activa").sum() == activas
    assert todas["cuil"].astype(str).str.contains("-").all()
    assert {"Directora", "Codirectora"} <= set(todas["rol"])
    h = todas.set_index("id")["horas_asignadas"]
    assert float(h.loc[53]) == 2.5
    assert all(float(h.loc[i]) == 0 for i in (60, 67, 69, 72, 83, 87, 90))
    assert 173 in set(todas["id"])
    assert len(L.proyectos()) == 61
    assert date(2026, 10, 26) == FIXED_TODAY
