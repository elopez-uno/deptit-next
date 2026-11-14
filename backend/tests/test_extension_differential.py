"""Diferenciales de LECTURA de Extension: funciones certificadas (``certified_extension``, pagina l. 65649-66417) vs
NEXT (``extension.lecturas.Lecturas`` / Excel), sobre ``deptit_next_dev`` real dentro de una transaccion que se revierte.

Cubre: catalogo v199 (todos, vigentes por periodo, sin periodo), ``get_extension_docente`` (local, institucional, con
bajas, foto al cierre v183, enriquecimiento v277), periodo actual / historico cerrado / historico ABIERTO por excepcion
(con datos sinteticos ``ZZNEXT``: los datos reales de Extension no tienen historico, bajas, suspendidos ni 0 hs),
padron v276 (el mismo de Investigacion), capacidad v184 con y sin exclusion (``excluir_tipo="extension"``) compartida
con Investigacion, excesos v184, duplicado e integrantes v217, actos v263 y el Excel integral (byte a byte salvo
``docProps/core.xml``)."""

from __future__ import annotations

import zipfile
from datetime import date
from decimal import Decimal
from io import BytesIO

import pandas as pd
import psycopg
import pytest

from comisiones.service import _jsonable
from extension import excel as X
from extension.lecturas import Lecturas
from extension.repository import ExtensionRepository
from investigacion.lecturas import Lecturas as LecturasInvestigacion
from investigacion.repository import InvestigacionRepository
from extension_support import (  # noqa: F401  (fixtures)
    FIXED_TODAY, audit_store, certified_extension, db_conn, extension, lock_conn, session_for,
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
    return Lecturas(ExtensionRepository(db_conn, INST, dep), FIXED_TODAY, rol)


def _periodos(db_conn, dep):
    return {r[1]: r[0] for r in db_conn.execute(
        "SELECT id, nombre FROM periodos WHERE institucion_id=%s AND departamento_id=%s", [INST, dep]).fetchall()}


@pytest.mark.parametrize("dep", [1, 2, 3])
def test_catalogo_v199(db_conn, dep):
    ns = certified_extension(db_conn, INST, dep)
    L = lecturas(db_conn, dep)
    igual(ns["get_proyectos_extension"](), L.proyectos(), "catalogo")
    igual(ns["get_proyectos_extension"](solo_activos=True), L.proyectos(solo_activos=True), "activos")
    for nombre, pid in _periodos(db_conn, dep).items():
        igual(ns["get_proyectos_extension"](solo_activos=True, periodo_id=pid),
              L.proyectos(solo_activos=True, periodo_id=pid), f"vigentes {nombre}")


@pytest.mark.parametrize("dep", [1, 2, 9])
def test_asignaciones_local_e_institucional(db_conn, dep):
    ns = certified_extension(db_conn, INST, dep)
    L = lecturas(db_conn, dep)
    g = ns["get_extension_docente"]
    for nombre, pid in _periodos(db_conn, dep).items():
        hist = ns["es_periodo_historico_contexto_v182"](pid)
        assert hist == L.es_historico(pid)
        igual(g(periodo_id=pid, incluir_bajas=hist), L.asignaciones(periodo_id=pid, incluir_bajas=hist), f"tab4 {nombre}")
        igual(g(periodo_id=pid), L.asignaciones(periodo_id=pid), f"activas/foto {nombre}")
        igual(g(periodo_id=pid, todos_departamentos=True), L.asignaciones(periodo_id=pid, todos_departamentos=True),
              f"institucional {nombre}")
    igual(g(incluir_bajas=True, todos_departamentos=True), L.asignaciones(incluir_bajas=True, todos_departamentos=True),
          "historial institucional")


def _sinteticos(db_conn):
    """Proyectos y asignaciones ZZNEXT del dep 1 (dentro de la transaccion del test): Activo vigente en 2026, Suspendido,
    y en 2026-1 (Cerrado): activa, activa con 0 hs, baja POSTERIOR al cierre (entra en la foto) y baja anterior."""
    per = _periodos(db_conn, 1)
    cuiles = [r[0] for r in db_conn.execute(
        "SELECT cuil FROM docentes WHERE institucion_id=1 AND departamento_id=1 ORDER BY id LIMIT 4").fetchall()]
    ids = {}
    for clave, estado in (("A", "Activo"), ("S", "Suspendido")):
        ids[clave] = db_conn.execute(
            "INSERT INTO proyectos_extension (institucion_id, departamento_id, nombre_proyecto, codigo_proyecto, "
            "instituto_proyecto, anio_llamado, fecha_inicio, fecha_fin, periodo_ejecucion, observaciones, estado, "
            "fecha_carga) VALUES (1, 1, %s, %s, '', 2025, '2026-01-01', '2026-12-31', '01/01/2026 al 31/12/2026', '', "
            "%s, '2026-01-10') RETURNING id", [f"ZZNEXT Ext {clave}", f"ZZNEXT-E{clave}", estado]).fetchone()[0]
    filas = [("A", cuiles[0], 5, "Activa", None), ("A", cuiles[1], 0, "Activa", None),
             ("A", cuiles[2], 3, "Baja", "2026-08-15"), ("A", cuiles[3], 2, "Baja", "2026-03-01"),
             ("S", cuiles[0], 4, "Activa", None)]
    for clave, cuil, hs, estado, baja in filas:
        db_conn.execute(
            "INSERT INTO extension_docente (institucion_id, departamento_id, proyecto_id, periodo_id, cuil, "
            "nombre_proyecto, rol, anio_llamado, periodo_ejecucion, horas_asignadas, observaciones, fecha_carga, "
            "codigo_proyecto, instituto_proyecto, estado_asignacion, fecha_baja, motivo_baja) VALUES (1, 1, %s, %s, %s, "
            "%s, 'Integrante', 2025, '01/01/2026 al 31/12/2026', %s, '', '2026-02-01', %s, '', %s, %s, %s)",
            [ids[clave], per["2026-1"], cuil, f"ZZNEXT Ext {clave}", hs, f"ZZNEXT-E{clave}", estado, baja,
             "ZZNEXT" if baja else None])
    return ids, per


def test_foto_al_cierre_y_proyecto_suspendido(db_conn):
    """2026-1 (Cerrado) del dep 1 con datos ZZNEXT: foto al cierre (activas, 0 hs y la baja posterior al cierre), el
    proyecto Suspendido no vigente ni en el historico (comportamiento heredado) y la pestaña 4 con bajas."""
    with db_conn.transaction():
        ids, per = _sinteticos(db_conn)
        ns = certified_extension(db_conn, INST, 1)
        L = lecturas(db_conn, 1)
        pid = per["2026-1"]
        assert L.es_historico(pid)
        foto = L.asignaciones(periodo_id=pid)
        igual(ns["get_extension_docente"](periodo_id=pid), foto, "foto")
        igual(ns["get_extension_docente"](periodo_id=pid, incluir_bajas=True),
              L.asignaciones(periodo_id=pid, incluir_bajas=True), "tab4 historico")
        vig = L.proyectos(solo_activos=True, periodo_id=pid)
        igual(ns["get_proyectos_extension"](solo_activos=True, periodo_id=pid), vig, "vigentes historico")
        assert ids["S"] not in set(vig["id"].astype(int)) and ids["A"] in set(vig["id"].astype(int))
        igual(ns["get_proyectos_extension"](), L.proyectos(), "catalogo con suspendido")
        assert 0.0 in set(foto["horas_asignadas"].astype(float))
        raise psycopg.Rollback()


def test_historico_abierto_por_excepcion(db_conn):
    """Abrir 2026-1 por excepcion (transaccion revertida): lecturas con foto al cierre, capacidad y excesos."""
    with db_conn.transaction():
        _, per = _sinteticos(db_conn)
        db_conn.execute("UPDATE periodos SET estado='Cerrado' WHERE institucion_id=1 AND departamento_id=1")
        db_conn.execute("UPDATE periodos SET estado='Abierto' WHERE id=%s", [per["2026-1"]])
        ns = certified_extension(db_conn, INST, 1)
        L = lecturas(db_conn, 1)
        ab = L.periodo_abierto()
        assert ab["id"] == per["2026-1"] and L.es_historico(ab["id"])
        igual(ns["get_proyectos_extension"](solo_activos=True, periodo_id=ab["id"]),
              L.proyectos(solo_activos=True, periodo_id=ab["id"]), "vigentes historico")
        editar = L.asignaciones(periodo_id=ab["id"])
        igual(ns["get_extension_docente"](periodo_id=ab["id"]), editar, "editar/bajas")
        assert not editar.empty
        for _, r in editar.iterrows():
            assert ns["capacidad_proyectos_docente_v184"](r["cuil"], ab["id"]) == L.capacidad(r["cuil"], ab["id"])
            assert ns["capacidad_proyectos_docente_v184"](r["cuil"], ab["id"], excluir_tipo="extension",
                                                          excluir_id=int(r["id"])) == \
                L.capacidad(r["cuil"], ab["id"], "extension", int(r["id"]))
        igual(ns["detectar_excesos_proyectos_v184"](ab["id"], "extension"), L.detectar_excesos(ab["id"]), "excesos")
        raise psycopg.Rollback()


def test_padron_v276(db_conn):
    ns = certified_extension(db_conn, INST, 1)
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
    ns = certified_extension(db_conn, INST, 1)
    L = lecturas(db_conn, 1)
    pid = _periodos(db_conn, 1)["2026-2"]
    asig = L.asignaciones(periodo_id=pid)
    assert not asig.empty
    for _, r in asig.iterrows():
        cuil, aid = r["cuil"], int(r["id"])
        assert ns["capacidad_proyectos_docente_v184"](cuil, pid) == L.capacidad(cuil, pid)
        assert ns["capacidad_proyectos_docente_v184"](cuil, pid, excluir_tipo="extension", excluir_id=aid) == \
            L.capacidad(cuil, pid, "extension", aid)
    igual(ns["detectar_excesos_proyectos_v184"](pid, "extension"), L.detectar_excesos(pid), "excesos")
    for cuil in asig["cuil"].head(3):
        igual(ns["_detalle_proyectos_docente_v187"](cuil, pid), L.detalle_proyectos_docente_v187(cuil, pid), "v187")


@pytest.mark.parametrize("dep", [1, 4])
def test_duplicado_e_integrantes_v217(db_conn, dep):
    ns = certified_extension(db_conn, INST, dep)
    L = lecturas(db_conn, dep)
    pid = _periodos(db_conn, dep)["2026-2"]
    for proyecto in L.proyectos(solo_activos=True, periodo_id=pid)["id"].head(12):
        integ = L.integrantes(int(proyecto), pid)
        igual(ns["get_integrantes_activos_proyecto_periodo_extension"](int(proyecto), pid), integ, f"integrantes {proyecto}")
        for _, r in integ.head(2).iterrows():
            a = ns["buscar_asignacion_activa_docente_proyecto_extension"](pid, int(proyecto), r["cuil"], todos_departamentos=True)
            b = L.buscar_activa(pid, int(proyecto), r["cuil"])
            assert {k: _norm(v) for k, v in a.items()} == {k: _norm(v) for k, v in b.items()}
            assert L.buscar_activa(pid, int(proyecto), r["cuil"], excluir_id=int(r["id"])) == \
                (ns["buscar_asignacion_activa_docente_proyecto_extension"](pid, int(proyecto), r["cuil"], excluir_id=int(r["id"]),
                                                                   todos_departamentos=True) or {})


def test_actos_v263(db_conn):
    ns = certified_extension(db_conn, INST, 1)
    L = lecturas(db_conn, 1)
    ids = L.proyectos()["id"].astype(int).tolist()
    igual(ns["get_documentos_proyectos_v263"]("extension", ids), L.documentos_proyectos(ids), "actos")


def _partes(contenido: bytes) -> dict:
    with zipfile.ZipFile(BytesIO(contenido)) as z:
        return {n: z.read(n) for n in sorted(z.namelist()) if n != "docProps/core.xml"}


@pytest.mark.parametrize("dep", [1, 2])
def test_excel_integral_byte_a_byte(db_conn, dep):
    ns = certified_extension(db_conn, INST, dep)
    L = lecturas(db_conn, dep)
    pid = _periodos(db_conn, dep)["2026-2"]
    cert = ns["generar_excel_modelo_proyectos_v217"]("extension", pid)
    nxt = X.integral_v217(L.proyectos(), L.padron(), L.asignaciones(periodo_id=pid, incluir_bajas=False))
    assert _partes(cert) == _partes(nxt)
    # Sin periodo abierto: hoja de asignaciones vacia.
    assert _partes(ns["generar_excel_modelo_proyectos_v217"]("extension", None)) == \
        _partes(X.integral_v217(L.proyectos(), pd.DataFrame(), pd.DataFrame()))
    # Lectura del propio modelo: mismas filas que el lector certificado.
    igual(ns["leer_excel_carga_rapida_proyectos_v127"](nxt), X.leer_carga_rapida_v127(nxt), "leer v127")
    igual(ns["leer_asignaciones_proyectos_excel_v217"](nxt), X.leer_asignaciones_v217(nxt), "leer v217")


def test_capacidad_compartida_con_investigacion_y_excesos_reales(db_conn):
    """El mismo tope para Investigacion + Extension: la capacidad vista desde Extension es la vista desde Investigacion
    (y la certificada) para los 17 CUIL con Extension activa; las 6 asignaciones con exceso del relevamiento."""
    filas = db_conn.execute("SELECT id, departamento_id, periodo_id, cuil FROM extension_docente "
                            "WHERE estado_asignacion='Activa' ORDER BY id").fetchall()
    assert len(filas) == 17
    con_exceso = []
    for aid, dep, per, cuil in filas:
        ns = certified_extension(db_conn, INST, dep)
        cap_ext = lecturas(db_conn, dep).capacidad(cuil, per)
        cap_inv = LecturasInvestigacion(InvestigacionRepository(db_conn, INST, dep), FIXED_TODAY,
                                        "usuario_departamento").capacidad(cuil, per)
        assert cap_ext == cap_inv == ns["capacidad_proyectos_docente_v184"](cuil, per)
        assert lecturas(db_conn, dep).capacidad(cuil, per, "extension", aid) == \
            ns["capacidad_proyectos_docente_v184"](cuil, per, excluir_tipo="extension", excluir_id=aid)
        if cap_ext["exceso_proyectos"] > 0:
            con_exceso.append(aid)
    assert con_exceso == [6, 7, 9, 10, 12, 13]


def test_datos_legacy_preservados(db_conn):
    """Casos del relevamiento (§13): CUIL con guiones, roles libres, 7,5 hs, asignacion 3 sin movimiento (no se repara)."""
    L = lecturas(db_conn, 1)
    todas = L.asignaciones(incluir_bajas=True, todos_departamentos=True)
    assert len(todas) == 17 and (todas["estado_asignacion"] == "Activa").all()
    assert todas["cuil"].astype(str).str.contains("-").all()
    assert {"Investigadora", "Directora", "Codirectora"} <= set(todas["rol"])
    assert float(todas.set_index("id")["horas_asignadas"].loc[4]) == 7.5
    assert len(L.proyectos()) == 14 and set(L.proyectos()["estado"]) == {"Activo"}
    sin_mov = db_conn.execute("""
        SELECT e.id FROM extension_docente e WHERE NOT EXISTS (SELECT 1 FROM movimientos m
          WHERE m.tipo_movimiento='Asignación a extensión' AND m.periodo_id=e.periodo_id
            AND m.departamento_id=e.departamento_id
            AND regexp_replace(m.cuil,'[^0-9]','','g')=regexp_replace(e.cuil,'[^0-9]','','g'))""").fetchall()
    assert [r[0] for r in sin_mov] == [3]
    assert db_conn.execute("SELECT count(*) FROM documentos_respaldo_proyectos WHERE proyecto_tipo='extension' "
                           "AND departamento_id=1").fetchone()[0] == 14
    assert date(2026, 10, 26) == FIXED_TODAY
