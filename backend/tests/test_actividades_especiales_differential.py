"""Diferenciales de LECTURA de Actividades Especiales: funciones certificadas (``certified_actividades``, pagina
l. 66418-66603) vs NEXT (``ActividadesRepository`` / servicio), sobre ``deptit_next_dev`` real dentro de una
transaccion que se revierte.

Cubre: actividades del periodo (todas / solo activas), participaciones locales (por periodo, historial, con bajas, por
CUIL), ambito departamental, lectura institucional G5 (periodo equivalente, con y sin bajas, por CUIL), selector de
docentes (base maestra ``get_docentes``), estados Activa/Finalizada/Suspendida y periodos abiertos y cerrados con datos
sinteticos ``ZZNEXT``, y los datos reales sin normalizar."""

from __future__ import annotations

from decimal import Decimal

import pandas as pd
import psycopg
import pytest

from actividades_especiales import rules as AR
from actividades_especiales.repository import ActividadesRepository
from actividades_especiales.service import ActividadesService
from actividades_support import (  # noqa: F401  (fixtures)
    FIXED_TODAY, actividades, audit_store, certified_actividades, db_conn, session_for,
)
from comisiones.service import _jsonable

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")

INST = 1


def _norm(v):
    v = _jsonable(v)
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, Decimal):
        return float(v)
    return v


def _rows(df):
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return []
    return [{str(k): _norm(v) for k, v in r.items()} for r in df.to_dict(orient="records")]


def igual(a, b, contexto=""):
    ra, rb = _rows(a), _rows(b)
    if ra or rb:
        assert list(a.columns) == list(b.columns), f"{contexto}: columnas\ncert {list(a.columns)}\nnext {list(b.columns)}"
    assert ra == rb, f"{contexto}\ncert {ra[:3]}\nnext {rb[:3]}"


def _periodos(db_conn, dep):
    return {r[1]: r[0] for r in db_conn.execute(
        "SELECT id, nombre FROM periodos WHERE institucion_id=%s AND departamento_id=%s", [INST, dep]).fetchall()}


def sinteticos(db_conn):
    """Dep 1: actividades ZZNEXT Activa en 2026-1 (Cerrado), Finalizada y Suspendida en 2026-2, con participaciones
    (una en otro formato de CUIL y una con estado heredado 'Baja')."""
    per = _periodos(db_conn, 1)
    cuiles = [r[0] for r in db_conn.execute(
        "SELECT cuil FROM docentes WHERE institucion_id=1 AND departamento_id=1 ORDER BY id LIMIT 3").fetchall()]
    ids = {}
    for clave, periodo, estado in (("H", "2026-1", "Activa"), ("F", "2026-2", "Finalizada"), ("S", "2026-2", "Suspendida")):
        ids[clave] = db_conn.execute(
            "INSERT INTO actividades_especiales (institucion_id, departamento_id, periodo_id, titulo, descripcion, estado, "
            "observaciones, fecha_carga) VALUES (1, 1, %s, %s, 'desc', %s, 'obs', '2026-03-01 10:00:00.000001') RETURNING id",
            [per[periodo], f"ZZNEXT {clave}", estado]).fetchone()[0]
    for clave, cuil, estado in (("H", cuiles[0], "Activa"), ("H", cuiles[1], "Baja"),
                                ("F", cuiles[0].replace("-", ""), "Activa"), ("S", cuiles[2], "Activa")):
        periodo = "2026-1" if clave == "H" else "2026-2"
        db_conn.execute(
            "INSERT INTO actividad_especial_docente (institucion_id, departamento_id, actividad_id, periodo_id, cuil, rol, "
            "estado_asignacion, observaciones, fecha_carga) VALUES (1, 1, %s, %s, %s, 'Coordinador', %s, '', "
            "'2026-03-02 11:00:00')", [ids[clave], per[periodo], cuil, estado])
    return ids, per


@pytest.mark.parametrize("dep", [1, 2, 3])
def test_actividades_y_participaciones_por_periodo(db_conn, dep):
    """Pestañas 1, 3, 4 y 5: mismas filas que ``get_actividades_especiales`` / ``..._docente`` (rama local)."""
    ns = certified_actividades(db_conn, INST, dep)
    repo = ActividadesRepository(db_conn, INST, dep)
    igual(ns["get_actividades_especiales"](None, incluir_inactivas=True), repo.actividades(None, True), "editar")
    igual(ns["get_actividades_especiales_docente"](periodo_id=None, incluir_bajas=True, todos_departamentos=False),
          repo.participaciones_local(None, None, True), "historial")
    for nombre, pid in _periodos(db_conn, dep).items():
        igual(ns["get_actividades_especiales"](pid, incluir_inactivas=True), repo.actividades(pid, True), f"tab1 {nombre}")
        igual(ns["get_actividades_especiales"](pid, incluir_inactivas=False), repo.actividades(pid, False),
              f"tab3 {nombre}")
        igual(ns["get_actividades_especiales_docente"](periodo_id=pid, incluir_bajas=True, todos_departamentos=False),
              repo.participaciones_local(None, pid, True), f"participaciones {nombre}")
        igual(ns["get_actividades_especiales_docente"](periodo_id=pid, incluir_bajas=False, todos_departamentos=False),
              repo.participaciones_local(None, pid, False), f"activas {nombre}")


def test_sinteticos_estados_periodo_cerrado_y_bajas(db_conn):
    with db_conn.transaction():
        ids, per = sinteticos(db_conn)
        ns = certified_actividades(db_conn, INST, 1)
        repo = ActividadesRepository(db_conn, INST, 1)
        for pid in per.values():
            for inactivas in (True, False):
                igual(ns["get_actividades_especiales"](pid, incluir_inactivas=inactivas),
                      repo.actividades(pid, inactivas), f"{pid} {inactivas}")
            for bajas in (True, False):
                igual(ns["get_actividades_especiales_docente"](periodo_id=pid, incluir_bajas=bajas),
                      repo.participaciones_local(None, pid, bajas), f"part {pid} {bajas}")
        igual(ns["get_actividades_especiales_docente"](incluir_bajas=True), repo.participaciones_local(None, None, True),
              "historial con sinteticos")
        activas_2026_2 = set(repo.actividades(per["2026-2"], False)["id"].astype(int))
        assert ids["F"] not in activas_2026_2 and ids["S"] not in activas_2026_2  # no se ofrecen en "Asignar"
        assert ids["H"] in set(repo.actividades(per["2026-1"], False)["id"].astype(int))  # periodo cerrado
        cuil = db_conn.execute("SELECT cuil FROM docentes WHERE institucion_id=1 AND departamento_id=1 ORDER BY id LIMIT 1"
                               ).fetchone()[0]
        for bajas in (True, False):
            igual(ns["get_actividades_especiales_docente"](cuil=cuil, periodo_id=per["2026-1"], incluir_bajas=bajas),
                  repo.participaciones_local(cuil, per["2026-1"], bajas), "por cuil")
        raise psycopg.Rollback()


def test_ambito_departamental(db_conn):
    """Cada departamento ve solo lo suyo (inyector de ambito): el dep 1 no ve la actividad del dep 2 y viceversa."""
    uno = ActividadesRepository(db_conn, INST, 1).actividades(None, True)
    dos = ActividadesRepository(db_conn, INST, 2).actividades(None, True)
    assert set(uno["id"].astype(int)) == {1} and set(dos["id"].astype(int)) == {2}
    assert ActividadesRepository(db_conn, INST, 3).actividades(None, True).empty


@pytest.mark.parametrize("dep", [1, 2, 4])
def test_lectura_institucional_g5(db_conn, dep):
    """``get_actividades_especiales_docente(todos_departamentos=True)``: rama institucional del futuro Resumen docente."""
    with db_conn.transaction():
        sinteticos(db_conn)
        ns = certified_actividades(db_conn, INST, dep)
        repo = ActividadesRepository(db_conn, INST, dep)
        g = ns["get_actividades_especiales_docente"]
        for pid in list(_periodos(db_conn, dep).values()) + [None]:
            for bajas in (True, False):
                igual(g(periodo_id=pid, incluir_bajas=bajas, todos_departamentos=True),
                      repo.participaciones_institucion(None, pid, bajas), f"inst {pid} {bajas}")
        for cuil in [r[0] for r in db_conn.execute("SELECT DISTINCT cuil FROM actividad_especial_docente LIMIT 4")]:
            igual(g(cuil=cuil, periodo_id=_periodos(db_conn, dep)["2026-2"], todos_departamentos=True),
                  repo.participaciones_institucion(cuil, _periodos(db_conn, dep)["2026-2"], False), "inst cuil")
        raise psycopg.Rollback()


@pytest.mark.parametrize("dep", [1, 2])
def test_selector_de_docentes_base_maestra(db_conn, dep):
    """l. 66497-66504: ``get_docentes()`` efectiva (v281 off) y la etiqueta "Nombre - CUIL", en el mismo orden."""
    ns = certified_actividades(db_conn, INST, dep)
    df = ns["get_docentes"]()
    opciones = {}
    for _, r in df.iterrows():
        nom = ns["limpiar_texto_tabla"](r.get("nombre_completo")) or ns["nombre_completo"](r.get("apellido", ""), r.get("nombres", "")) \
            or ns["limpiar_texto_tabla"](r.get("nombre")) or ns["limpiar_texto_tabla"](r.get("cuil"))
        opciones[f"{nom} - {r.get('cuil','')}"] = str(r.get("cuil") or "")
    nxt = ActividadesService._docentes_selector(ActividadesRepository(db_conn, INST, dep))
    assert [(o["etiqueta"], o["cuil"]) for o in nxt] == list(opciones.items())
    assert len(nxt) > 0


def test_estado_mostrado_safe_index():
    assert [AR.estado_mostrado(x) for x in ("Activa", "Finalizada", "Suspendida", "Otro", None)] == [
        "Activa", "Finalizada", "Suspendida", "Activa", "Activa"]


def test_datos_reales_preservados(db_conn):
    """§15: 2 actividades (dep 1 y 2, 2026-2, Activa), 6 participaciones Activas, CUIL con guiones, sin horas."""
    act = db_conn.execute("SELECT id, departamento_id, estado FROM actividades_especiales ORDER BY id").fetchall()
    assert act == [(1, 1, "Activa"), (2, 2, "Activa")]
    part = db_conn.execute("SELECT count(*), count(*) FILTER (WHERE estado_asignacion='Activa'), "
                           "count(*) FILTER (WHERE cuil ~ '-') FROM actividad_especial_docente").fetchone()
    assert part == (6, 6, 6)
    cols = {r[0] for r in db_conn.execute("SELECT column_name FROM information_schema.columns WHERE table_name IN "
                                          "('actividades_especiales','actividad_especial_docente')")}
    assert not any("hora" in c for c in cols)
    assert FIXED_TODAY.year == 2026
