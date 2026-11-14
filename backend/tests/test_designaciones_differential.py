"""Diferenciales de LECTURA de Designaciones: NEXT vs el codigo certificado ejecutado sobre la misma base.

Todo corre en la transaccion del test (ROLLBACK).  Departamentos reales de deptit_next_dev (institucion 1)."""

from __future__ import annotations

import pandas as pd
import pytest
from openpyxl import load_workbook

from designaciones import escrituras as E
from designaciones import excel, historial, rules
from designaciones.repository import DesignacionesRepository
from designaciones.service import DesignacionesService
from designaciones_support import (  # noqa: F401  (fixture)
    FIXED_TODAY, certified_designaciones, corregir_fecha_anio_primero, db_conn,
)

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")

DEPARTAMENTOS = (1, 2, 3, 4, 9, 11)


def _periodos(conn, dep):
    return [r[0] for r in conn.execute("SELECT id FROM periodos WHERE institucion_id=1 AND departamento_id=%s ORDER BY id",
                                       [dep]).fetchall()]


def _norm(v):
    if v is None or (isinstance(v, float) and v != v) or v is pd.NA:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(v, "item"):
        v = v.item()
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v)


def _service_data(conn, dep, pid):
    svc = DesignacionesService(None, None, None, today=lambda: FIXED_TODAY)
    return svc._periodo_data(DesignacionesRepository(conn, 1, dep), pid)


@pytest.mark.parametrize("dep", DEPARTAMENTOS)
def test_get_designaciones_equivalente_por_periodo(db_conn, dep):
    ns = certified_designaciones(db_conn, 1, dep)
    repo = DesignacionesRepository(db_conn, 1, dep)
    for pid in _periodos(db_conn, dep):
        cert = ns["get_designaciones"](pid)
        mine = DesignacionesService._designaciones(repo, pid)
        assert len(cert) == len(mine)
        por_id = {int(r["id"]): r for r in cert.to_dict(orient="records")}
        for m in mine:
            r = por_id[m["id"]]
            for k in r:
                a, b = _norm(r[k]), _norm(m.get(k))
                if a is None and b in (None, ""):
                    continue
                assert a == b, (pid, m["id"], k)
        # El ORDER BY certificado no desempata dentro de un mismo docente: se compara la secuencia de docentes.
        assert [r["nombre_completo"] for r in cert.to_dict(orient="records")] == [m["nombre_completo"] for m in mine]


@pytest.mark.parametrize("dep", DEPARTAMENTOS)
def test_historico_y_foto_al_cierre(db_conn, dep):
    ns = certified_designaciones(db_conn, 1, dep)
    for pid in _periodos(db_conn, dep):
        data = _service_data(db_conn, dep, pid)
        assert data["historico"] == ns["es_periodo_historico_contexto_v182"](pid)
        foto = ns["_filtrar_foto_designaciones_v169"](ns["get_designaciones"](pid), pid)
        ids = sorted(pd.to_numeric(foto.get("id", pd.Series(dtype=float))).dropna().astype(int).tolist())
        assert data["foto_ids"] == ids
        activas = int((ns["get_designaciones"](pid)["estado"] == "Activa").sum()) if not data["historico"] else len(ids)
        assert data["conteo"] == activas


def test_historico_con_periodo_anterior_abierto_por_excepcion(db_conn):
    """Abrir un período anterior lo vuelve "abierto" pero sigue siendo histórico (v182)."""
    db_conn.execute("UPDATE periodos SET estado='Cerrado' WHERE institucion_id=1 AND departamento_id=1")
    db_conn.execute("UPDATE periodos SET estado='Abierto' WHERE id=5")
    ns = certified_designaciones(db_conn, 1, 1)
    for pid in (5, 9):
        data = _service_data(db_conn, 1, pid)
        assert data["historico"] == ns["es_periodo_historico_contexto_v182"](pid)
        foto = ns["_filtrar_foto_designaciones_v169"](ns["get_designaciones"](pid), pid)
        assert data["foto_ids"] == sorted(int(x) for x in foto.get("id", []))
    assert _service_data(db_conn, 1, 5)["historico"] is True
    # El último período cerrado sin otro abierto también es histórico.
    db_conn.execute("UPDATE periodos SET estado='Cerrado' WHERE id=5")
    assert _service_data(db_conn, 1, 9)["historico"] is ns["es_periodo_historico_contexto_v182"](9) is True


@pytest.mark.parametrize("dep", (1, 2, 3, 9))
def test_historial_del_periodo_equivalente(db_conn, dep):
    from deptit_refactor.domain.movimientos import calcular_variacion_horas_movimiento, clasificar_movimiento_docente
    from deptit_refactor.extracted_batch04.movimientos import normalizar_tipo_movimiento_dedicacion

    ns = certified_designaciones(db_conn, 1, dep)
    for pid in _periodos(db_conn, dep):
        cert = ns["get_movimientos_designaciones_periodo_v266"](pid)
        data = _service_data(db_conn, dep, pid)
        assert len(cert) == len(data["historial"]), pid
        for (_, r), m in zip(cert.iterrows(), data["historial"]):
            var = calcular_variacion_horas_movimiento(r.get("tipo_movimiento", ""), r.get("detalle", ""),
                                                      r.get("horas_variacion", 0))
            cat = clasificar_movimiento_docente(normalizar_tipo_movimiento_dedicacion(r.get("tipo_movimiento", ""), var),
                                                var)
            assert int(r["id"]) == m["id"]
            assert (r["tipo_movimiento"], _norm(r.get("observaciones")), str(r.get("acto_administrativo") or "")) == \
                (m["tipo_movimiento"], _norm(m["observaciones"]), str(m["acto_administrativo"] or ""))
            assert _norm(r.get("acto_documento_id")) == _norm(m["acto_documento_id"])
            assert float(var) == m["variacion_horas"] and cat == m["categoria"]


CARGAS = [
    "cuil\tcargo\tdedicacion\tfecha_desde\tfecha_hasta\n20-11111111-1\tAdjunto\tParcial\t01/08/2026\t31/12/2026\n",
    "periodo\tcuil\tcargo\tdedicacion\thoras\ttipo_designacion\tnumero_resolucion\tad_honorem\tfecha_desde\tfecha_hasta"
    "\testado\tobservaciones\n2026-1\t20111111111\t\t\t99\t\tR-1\tsi\t2026-03-01\t2026-07-31\tActiva\tx\n"
    "\t\t\t\t\t\t\t\t\t\t\t\n\t20-22222222-2\tTitular\tExclusiva\t\tConcursado\t\tNo\t2024-01-01\t2027-12-31\t\t\n",
    "20-33333333-3;JTP;Simple;10;Interino;No;2026-08-01;2026-12-31;Activa;obs\n",
    "cuil,cargo\n,Adjunto\n",
    "",
]


@pytest.mark.parametrize("texto", CARGAS)
def test_parser_carga_rapida_equivalente(db_conn, texto):
    # Desviacion deliberada (docs/ETAPA5_FINAL_REMEDIATION.md): NEXT no invierte dia/mes en fechas año-primero.
    ns = corregir_fecha_anio_primero(certified_designaciones(db_conn, 1, 1))
    abierto = ns["get_periodo_abierto"]()
    cert = ns["parsear_designaciones_pegadas"](texto, abierto)
    repo = DesignacionesRepository(db_conn, 1, 1)
    mine = rules.parsear_designaciones_pegadas(texto, pd.DataFrame(repo.periods()), FIXED_TODAY)
    assert cert.reset_index(drop=True).astype(str).to_dict(orient="records") == \
        mine.reset_index(drop=True).astype(str).to_dict(orient="records")


def test_duplicados_e_inexistentes_carga_rapida(db_conn):
    fila = db_conn.execute("SELECT cuil, cargo, dedicacion, tipo_designacion, ad_honorem, fecha_desde, fecha_hasta, "
                           "estado, COALESCE(numero_resolucion,'') FROM designaciones WHERE periodo_id=9 ORDER BY id "
                           "LIMIT 1").fetchone()
    cuil, cargo, ded, tipo, adh, desde, hasta, estado, res = fila
    texto = ("cuil\tcargo\tdedicacion\ttipo_designacion\tad_honorem\tfecha_desde\tfecha_hasta\tnumero_resolucion\n"
             f"{cuil}\t{cargo}\t{ded}\t{tipo}\t{adh}\t{desde}\t{hasta}\t{res}\n"
             f"{cuil}\t{cargo}\t{ded}\t{tipo}\t{adh}\t{desde}\t{hasta}\t{res}\n"
             "20-99119911-1\tJTP\tSimple\tInterino\tNo\t2020-01-01\t2020-02-01\t\n")
    # Desviacion deliberada (docs/ETAPA5_FINAL_REMEDIATION.md): con las fechas ISO de la base invertidas, el
    # certificado ni siquiera detecta que la fila pegada ya existe; NEXT si.
    ns = corregir_fecha_anio_primero(certified_designaciones(db_conn, 1, 1))
    abierto = ns["get_periodo_abierto"]()
    df = ns["parsear_designaciones_pegadas"](texto, abierto)
    cert = ns["detectar_designaciones_duplicadas_carga"](df, abierto)
    svc = DesignacionesService(None, None, None, today=lambda: FIXED_TODAY)
    repo = DesignacionesRepository(db_conn, 1, 1)
    analisis = svc._analisis_carga(repo, rules.parsear_designaciones_pegadas(texto, pd.DataFrame(repo.periods()),
                                                                             FIXED_TODAY))
    assert cert.astype(str).to_dict(orient="records") == pd.DataFrame(analisis["duplicadas"]).astype(str).to_dict(
        orient="records")
    inexistentes = [{"fila_pegada": int(i) + 1, "cuil": r["cuil"]} for i, r in df.iterrows()
                    if ns["docente_existe"](r["cuil"]).empty]
    assert [{k: d[k] for k in ("fila_pegada", "cuil")} for d in analisis["inexistentes"]] == inexistentes
    assert len(inexistentes) == 1 and len(cert) >= 1


def _libro(data: bytes) -> dict:
    wb = load_workbook(__import__("io").BytesIO(data))
    out = {}
    for ws in wb.worksheets:
        out[ws.title] = {
            "celdas": [[c.value for c in row] for row in ws.iter_rows()],
            "validaciones": sorted((str(dv.formula1), str(dv.sqref)) for dv in ws.data_validations.dataValidation),
            "estado": ws.sheet_state,
            "comentarios": sorted((c.coordinate, c.comment.text) for row in ws.iter_rows() for c in row if c.comment),
        }
    out["_nombres"] = sorted((n, str(wb.defined_names[n].attr_text)) for n in wb.defined_names)
    return out


@pytest.mark.parametrize("dep", (1, 11))
def test_modelo_excel_equivalente(db_conn, dep):
    ns = certified_designaciones(db_conn, 1, dep)
    abierto = ns["get_periodo_abierto"]()
    cert = ns["generar_excel_modelo_carga_rapida_designaciones"](periodo_default=abierto, filas_modelo=50)
    repo = DesignacionesRepository(db_conn, 1, dep)
    mine = excel.generar_excel_modelo_carga_rapida_designaciones(repo.docentes(), repo.periods(),
                                                                 periodo_default=repo.open_period(), filas_modelo=50)
    assert _libro(cert) == _libro(mine)


@pytest.mark.parametrize("dep", (1, 2, 4, 9))
def test_cargo_prioritario_v200_equivalente(db_conn, dep):
    """Regla certificada de cargo prioritario (propio / prestado / jerarquía) para todo CUIL con asignación o
    designación del departamento, más un CUIL ajeno (cae al fallback histórico: cargo vacío)."""
    ns = certified_designaciones(db_conn, 1, dep)
    pid = db_conn.execute("SELECT id FROM periodos WHERE institucion_id=1 AND departamento_id=%s ORDER BY anio DESC, "
                          "semestre DESC, id DESC LIMIT 1", [dep]).fetchone()[0]
    cuiles = {r[0] for r in db_conn.execute(
        "SELECT cuil FROM asignaciones_docentes_comision WHERE institucion_id=1 AND departamento_id=%s UNION "
        "SELECT cuil FROM designaciones WHERE institucion_id=1 AND departamento_id=%s", [dep, dep]).fetchall()}
    cuiles.add("20-99119911-9")

    # Mapa completo v200 (todos los CUIL de la institucion con designacion activa equivalente o ficha local).
    cert_map = ns["_mapa_cargos_prioritarios_v200"](pid, dep, 1, 0)
    mine_map = E.mapa_cargos_prioritarios(DesignacionesRepository(db_conn, 1, dep), pid, dep)
    assert set(cert_map) == set(mine_map)
    assert {k: v["cargo"] for k, v in cert_map.items()} == {k: v["cargo"] for k, v in mine_map.items()}

    class _U:
        def read(self, fn):
            return fn(DesignacionesRepository(db_conn, 1, dep))

    muestra = sorted(c for c in cuiles if c)[:4] + ["20-99119911-9"]
    for cuil in muestra:
        cert = ns["obtener_cargo_prioritario_docente_periodo"](cuil, pid, dep)
        mine = E.cargo_prioritario(_U(), rules.limpiar_cuil(cuil), pid, dep)
        assert str(cert.get("cargo") or "") == str(mine.get("cargo") or ""), cuil

def test_existe_designacion_duplicada_equivalente(db_conn):
    ns = certified_designaciones(db_conn, 1, 1)
    repo = DesignacionesRepository(db_conn, 1, 1)
    filas = db_conn.execute("SELECT periodo_id, cuil, cargo, dedicacion, horas, tipo_designacion, ad_honorem, "
                            "fecha_desde, fecha_hasta, estado, COALESCE(numero_resolucion,''), "
                            "COALESCE(funcion_no_docente,0) FROM designaciones WHERE departamento_id=1 ORDER BY id "
                            "LIMIT 25").fetchall()
    for f in filas:
        for estado, res, func in [(f[9], None, None), (f[9], f[10], bool(f[11])), ("Finalizada", None, not f[11]),
                                  (f[9], "otra", None)]:
            cert = ns["existe_designacion_duplicada"](f[0], f[1], f[2], f[3], f[4], f[5], f[6], f[7], f[8], estado,
                                                      numero_resolucion=res, funcion_no_docente=func)
            mine = DesignacionesService._duplicada(repo, f[0], f[1], f[2], f[3], f[4], f[5], f[6], f[7], f[8],
                                                   estado, numero_resolucion=res, funcion_no_docente=func)
            assert cert == mine


def test_historial_clasificacion_e_indicadores():
    df = pd.DataFrame([
        {"id": 1, "tipo_movimiento": "Alta de designación", "detalle": "2026-2 - JTP - Simple - 10 hs - Interino",
         "horas_variacion": 0},
        {"id": 2, "tipo_movimiento": "Disminución de dedicación", "detalle": "Antes: x 10 hs / Ahora: y 20 hs",
         "horas_variacion": 0},
        {"id": 3, "tipo_movimiento": "Pase a Ad Honorem", "detalle": "", "horas_variacion": 0},
    ])
    base, ind = historial.clasificar_v267(df)
    assert base["categoria_movimiento_v267"].tolist() == ["Altas de designaciones", "Aumentos de dedicación",
                                                          "Pase a Ad Honorem"]
    assert [i["etiqueta"] for i in ind] == ["Altas designaciones", "Aumentos", "Pase a Ad Honorem"]


def test_excel_de_la_tabla_historica_equivalente(db_conn, service, repo):
    """entry l. 63415-63442 + ``_convertir_tabla_a_excel_bytes`` (hoja "Datos")."""
    import io

    from designaciones_support import make_designaciones, session_for
    from periodos_support import FakeAuditStore
    ns = certified_designaciones(db_conn, 1, 1)
    df = ns["get_designaciones"](5)
    mostrar = df.drop(columns=["id", "periodo_id", "numero_resolucion", "numero_resolucion_legacy",
                               "acto_documento_id", "acto_dependencia", "acto_fecha"], errors="ignore").copy()
    foto = ns["_filtrar_foto_designaciones_v169"](df, 5)
    ids = set(int(x) for x in foto["id"])
    mostrar["estado"] = ["Vigente al cierre" if int(i) in ids else ns["_estado_designacion_visible_v162"](e)
                         for i, e in zip(df["id"], mostrar["estado"])]
    mostrar["funcion_no_docente"] = mostrar["funcion_no_docente"].map(
        lambda x: "No docente" if ns["_es_funcion_no_docente_v162"](x) else "Docencia")
    mostrar = mostrar.rename(columns={"acto_administrativo": "Acto administrativo", "funcion_no_docente": "Función",
                                      "texto_funcion_no_docente": "Funciones no docentes"})
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        mostrar.to_excel(writer, index=False, sheet_name="Datos")
    svc = make_designaciones(service, FakeAuditStore(), db_conn)
    mine, nombre = svc.periodo_excel(session_for(service, repo, 3)[0], 5)
    assert nombre == "Designaciones_20261026_103000.xlsx"
    a = load_workbook(io.BytesIO(out.getvalue()))["Datos"]
    b = load_workbook(io.BytesIO(mine))["Datos"]
    filas_a = [[c.value for c in r] for r in a.iter_rows()]
    filas_b = [[c.value for c in r] for r in b.iter_rows()]
    assert filas_a[0] == filas_b[0]
    assert sorted(map(repr, filas_a[1:])) == sorted(map(repr, filas_b[1:]))
