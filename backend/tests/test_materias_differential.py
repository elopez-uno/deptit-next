"""Equivalencia de las LECTURAS y reglas puras de Materias con el codigo certificado de reference_fix02.

Las funciones del entry corren sin cambios con la conexion "planes" certificada (inyector v193 + B12J) sobre
deptit_next_dev, para las 3 instituciones reales, y se comparan con NEXT.
"""

from __future__ import annotations

import io
import json

import pandas as pd
import pytest
from openpyxl import load_workbook

import unidades_support as U
from materias import excel, rules
from materias.repository import MateriasRepository
from materias_support import audit_store, certified_materias, db_conn, materias, uba_sintetica  # noqa: F401  (fixtures)

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")

INSTITUCIONES = (1, 2, 5)


def norm(df):
    if df is None:
        return []
    return json.loads(df.to_json(orient="records", force_ascii=False, default_handler=str))


def same(a, b):
    assert norm(a) == norm(b)


# ------------------------------------------------------------------------------------------------ reglas puras
CODIGOS = ["05-001", "5001", "8049.0", "09 027", "00-009OLAP", "", None, "abc-12", "1", "123456", "  7 ", "01.1",
           float("nan"), 8049.0, "8049.00", "Ñ-1"]


def test_pure_rules_equivalent(db_conn):
    ns = certified_materias(db_conn, 1)
    for c in CODIGOS:
        assert rules.normalizar_codigo_materia(c) == ns["normalizar_codigo_materia"](c), c
        assert rules.valor_limpio_materia(c) == ns["_valor_limpio_materia"](c)
    for v in ["", None, "Todas", "Escribir manualmente", " Escuela X "]:
        assert rules.escuela_para_filtro(v) == ns["escuela_para_filtro"](v)
    for a in ["Optativa I", "ELECTIVA", "Optativa Electiva", "Matemática", None, "  optativa  ii "]:
        assert rules.tipo_espacio_curricular_v120("", a) == ns["tipo_espacio_curricular_v120"]("", a)
        assert rules.es_materia_optativa_electiva("", a) == ns["es_materia_optativa_electiva"]("", a)
    for t in ["optativa", " ELECTIVA ", "x", None]:
        assert rules.normalizar_tipo_opcion_v120(t) == ns["_normalizar_tipo_opcion_v120"](t)
    for m in [None, "", "individual", "grupo", "Específica de esta carrera/plan", "Seleccionada", "x", "ESPECIFICO"]:
        assert rules.normalizar_modo_comparticion_v137(m) == ns["_normalizar_modo_comparticion_v137"](m)
    filas = [None, {}, {"materia_id": 7, "comparticion_modo": "Específica"}, {"id": 3, "codigo": "1", "asignatura": "A"},
             {"materia_id": 1, "comparticion_modo": "Seleccionada", "comparticion_grupo": " G1 "},
             {"materia_id": 1, "comparticion_modo": "Seleccionada"}]
    for f in filas:
        assert rules.clave_materia_conceptual_v137(f) == ns["_clave_materia_conceptual_v137"](f)
    fila = {"materia_id": 9, "tipo_espacio": "Optativa", "escuela": "E", "carrera": "C", "plan_version": "P",
            "codigo": "01", "asignatura": "Optativa I", "anio": "1° Año", "cuatrimestre": "2"}
    assert rules.etiqueta_espacio_plan_opcion_v124(fila) == ns["_etiqueta_espacio_plan_opcion_v124"](fila)
    assert rules.etiqueta_plan_materia_v137(fila) == ns["_etiqueta_plan_materia_v137"](fila)
    for h in ["Habilitación 11", "Código de la opción", " Facultad/Escuela oferente "]:
        assert rules.normalizar_encabezado_opcion_v124(h) == ns["_normalizar_encabezado_opcion_v124"](h)
    for vals in [["a", " a ", None, float("nan"), "b"], pd.Series(["x", None, "x"]), "solo"]:
        assert rules.deptit_join_unicos(vals) == ns["_deptit_join_unicos"](vals)


PLANES = [
    "codigo\tasignatura\tanio\tcuatrimestre\tcarga_semanal\tcarga_total\n05-001\tMatemática\t1\t1\t4\t64\n"
    "05-002\tFísica\t2.0\tAnual\t6\t96\n",
    "01-1;Taller;3°;2;;\n01-1;Otro nombre;1 año;1.0;x;10\n;;;;;\n",
    "Cod. Materia,Nombre,Año,Cuat,Modalidad,Hs semanales,Hs totales,Duración,Nro\n8049,Álgebra,1,1,Virtual,4,64,Anual,3\n",
    "", "  ",
]


@pytest.mark.parametrize("texto", PLANES)
def test_plan_parser_and_table_conflicts_equivalent(db_conn, texto):
    ns = certified_materias(db_conn, 1)
    exp = ns["parsear_plan_pegado"](texto)
    got = rules.parsear_plan_pegado(texto)
    same(got, exp)
    same(rules.detectar_conflictos_codigo_en_tabla(got), ns["detectar_conflictos_codigo_en_tabla"](exp))


# ------------------------------------------------------------------------------------------------ lecturas
def test_reads_equivalent_for_every_institution(db_conn, materias, uba_sintetica):
    for inst in INSTITUCIONES:
        ns = certified_materias(db_conn, inst)
        repo = MateriasRepository(db_conn, inst)
        same(repo.carreras(), ns["get_carreras"]())
        for estado in ("Activa", "Inactiva"):
            same(repo.carreras(estado=estado), ns["get_carreras"](estado=estado))
        assert repo.escuelas() == ns["get_facultades_escuelas_disponibles"]()
        for esc in repo.escuelas()[:2]:
            same(repo.carreras(escuela=esc), ns["get_carreras"](escuela=esc))
            assert materias._opciones_carreras(repo, escuela=esc) == ns["get_opciones_carreras"](escuela=esc)
        assert materias._opciones_carreras(repo, solo_activas=False) == ns["get_opciones_carreras"](solo_activas=False)
        same(repo.plan_todas(), ns["get_plan_estudio_todas"]())
        for cid in repo.carreras()["id"].tolist() if not repo.carreras().empty else []:
            same(repo.plan(cid), ns["get_plan_estudio"](cid))
            assert (repo.carrera(cid) or {}) == (ns["get_carrera"](cid) or {})
        todas = repo.plan_todas()
        for kwargs in [{}, {"estado": "Activa"}, {"cuatrimestre": "1 y 2"},
                       {"escuela": (repo.escuelas() or [None])[0]}]:
            same(materias._totales_df(todas, **kwargs), ns["get_materias_totales"](**kwargs))
            same(rules.materias_unicas(materias._totales_df(todas, **kwargs)), ns["get_materias_unicas"](**kwargs))
        base = rules.asegurar_columnas_materias(todas)
        same(base, ns["_asegurar_columnas_materias"](ns["get_plan_estudio_todas"]()))
        assert rules.opciones_carrera_plan_desde_materias(base) == ns["_opciones_carrera_plan_desde_materias"](base)
        for q in ["01-1", "011", "Taller", "matem", "zzz"]:
            same(rules.filtrar_busqueda_materias(base, q, ["carrera", "escuela", "plan_version"]),
                 ns["_filtrar_busqueda_materias"](base, q, ["carrera", "escuela", "plan_version"]))


def test_sharing_groups_and_identity_equivalent(db_conn, materias):
    repo = MateriasRepository(db_conn, 1)
    ns = certified_materias(db_conn, 1)
    todas = repo.plan_todas()
    muestra = todas[todas["comparticion_modo"] != "Automática"]["id"].tolist()
    muestra += todas["id"].head(40).tolist() + todas[todas["en_plan"] == 0]["id"].head(5).tolist()
    for mid in muestra:
        assert materias._ids_grupo(repo, mid) == ns["_ids_grupo_comparticion_materia_v137"](mid), mid
        assert materias._ids_grupo(repo, mid, False) == ns["_ids_grupo_comparticion_materia_v137"](mid, False)
        same(materias._apariciones_misma_identidad(repo, mid), ns["get_apariciones_misma_identidad_v137"](mid))
        same(materias._apariciones_misma_identidad(repo, mid, False),
             ns["get_apariciones_misma_identidad_v137"](mid, False))
    filas = todas.head(60)
    for _, r in filas.iterrows():
        exp = ns["obtener_conflictos_codigo_materia"](r["codigo"], "Otro nombre distinto")
        same(materias.obtener_conflictos_codigo_materia(repo, r["codigo"], "Otro nombre distinto"), exp)
        same(materias.existe_materia_duplicada(repo, r["carrera_id"], r["codigo"], r["asignatura"]),
             ns["existe_materia_duplicada"](r["carrera_id"], r["codigo"], r["asignatura"]))
    referenciadas = materias._ids_referenciados(repo, todas["id"].tolist())
    assert referenciadas == ns["_ids_materias_referenciadas_por_comisiones"](todas["id"].tolist())
    assert len(referenciadas) > 100


def test_opciones_curriculares_reads_equivalent(db_conn, materias, uba_sintetica):
    for inst in INSTITUCIONES:
        repo = MateriasRepository(db_conn, inst)
        ns = certified_materias(db_conn, inst)
        for tipo, estado in [(None, None), ("Optativa", None), ("Electiva", "Activa"), (None, "Inactiva")]:
            same(materias._opciones_enriquecidas(repo, tipo, estado),
                 ns["_get_opciones_curriculares_v120_no_cache_v127"](tipo=tipo, estado=estado))
        for tipo in (None, "Optativa", "Electiva"):
            for vig in (True, False):
                same(materias._espacios(repo, tipo, vig), ns["get_espacios_optativos_electivos_v120"](tipo, vig))
        ops = repo.opciones()
        ids = ops["id"].tolist() if not ops.empty else []
        for vig in (True, False):
            same(materias._vinculos_lote(repo, ids, vig), ns["_get_vinculos_opciones_lote_v127"](ids, vig))
        df, e2i, i2e = materias._catalogo_espacios(repo)
        cdf, ce2i, ci2e = ns["_catalogo_espacios_plan_opcion_v124"]()
        same(df, cdf)
        assert (e2i, i2e) == (ce2i, ci2e)


def test_excel_model_equivalent(db_conn, materias, service, repo):
    from materias_support import session_for
    record = session_for(service, repo, 3)[0]
    ns = certified_materias(db_conn, 1)
    expected = load_workbook(io.BytesIO(ns["generar_excel_modelo_carga_rapida_opciones_v124"]()))
    got = load_workbook(io.BytesIO(materias.modelo_excel(record)))
    assert got.sheetnames == expected.sheetnames
    for name in got.sheetnames:
        a, b = got[name], expected[name]
        assert (a.max_row, a.max_column, a.sheet_state) == (b.max_row, b.max_column, b.sheet_state)
        for ra, rb in zip(a.iter_rows(), b.iter_rows()):
            for ca, cb in zip(ra, rb):
                # 6A-B3: etiquetas "Unidad académica" decididas (unidades_support); el resto idéntico
                assert (ca.value, ca.number_format, ca.fill.fgColor.rgb) == (U.decidido_materias(cb.value),
                                                                             cb.number_format, cb.fill.fgColor.rgb)
                assert (ca.comment.text if ca.comment else None) == \
                       (U.decidido_materias(cb.comment.text) if cb.comment else None)
        assert [(d.formula1, str(d.sqref)) for d in a.data_validations.dataValidation] == \
               [(d.formula1, str(d.sqref)) for d in b.data_validations.dataValidation]
        assert [(t.name, t.ref) for t in a.tables.values()] == [(t.name, t.ref) for t in b.tables.values()]
    assert {k: v.attr_text for k, v in got.defined_names.items()} == \
           {k: v.attr_text for k, v in expected.defined_names.items()}
    contenido = materias.modelo_excel(record)
    historico = U.xlsx_con_encabezado_opciones(contenido, U.ENCABEZADO_OPCIONES_HISTORICO)
    leido = ns["leer_excel_carga_rapida_opciones_v124"](historico)
    assert "escuela_oferente" in leido.columns
    same(rules.leer_excel_carga_rapida_opciones_v124(contenido), leido)  # encabezado nuevo == histórico certificado
    same(rules.leer_excel_carga_rapida_opciones_v124(historico), leido)  # el histórico se sigue aceptando
    assert excel is not None
