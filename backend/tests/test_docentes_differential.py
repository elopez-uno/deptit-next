"""Equivalencia de Docentes con el codigo CERTIFICADO de reference_fix02 (solo lectura: sin bytecode, sin escrituras).

Cada caso ejecuta la funcion del entry sin cambios (``docentes_support.certified_docentes``) y la de NEXT sobre el MISMO
estado inicial de deptit_next_dev, dentro de SAVEPOINTs que se revierten, y compara el estado resultante de las 13 tablas
que referencian al docente por CUIL.
"""

from __future__ import annotations

import io
import json
import re
from datetime import date

import pandas as pd
import pytest
from openpyxl import load_workbook

from docentes import carga, identidad, rules
from docentes.repository import DocentesRepository
from docentes_support import (  # noqa: F401  (fixtures)
    ENTRY, FIXED_TODAY, audit_store, certified_docentes, db_conn, docentes, free_cuil, savepoint, session_for, state,
)

from deptit_refactor.b12a import posgrado as ref_b12a  # noqa: E402
from deptit_refactor.b13fix02 import validation as ref_validation  # noqa: E402
from deptit_refactor.extracted_batch04 import identidad as ref_identidad  # noqa: E402
from deptit_refactor.extracted_batch04 import texto as ref_texto  # noqa: E402

# El codigo certificado usa pandas.read_sql sobre una conexion DBAPI (aviso esperado de pandas).
pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")


def departments_with_docentes(conn):
    return conn.execute("SELECT DISTINCT institucion_id, departamento_id FROM docentes ORDER BY 1, 2").fetchall()


def _norm(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if hasattr(v, "item") and not isinstance(v, (str, bytes)):
        v = v.item()
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def records(df) -> list[dict]:
    return [{k: _norm(v) for k, v in r.items()} for r in df.to_dict(orient="records")]


# ------------------------------------------------------------------------------------------------ reglas puras
CUILS = ["20-12345678-9", "20123456789", "20 12345678 9", "20.12345678.9", " 27-12345678-3 ", "", None, "2012345678",
         "201234567890", "20-12345678-9X", "２０１２３４５６７８９", "20_12345678_9", "20-1234567-89", "x", "20/12345678/9",
         "20123456789.0", "  ", "20-12345678-9 ", "nan", "None"]
EMAILS = ["", None, "a@b.com", " docente@uno.edu.ar ", "a@b", "a b@c.com", "a@@b.com", "a@b.c", "@b.com", "a@b..com",
          "nombre@dominio.com.ar", "x@y.z.w"]


def test_k2_k3_validation_equivalent():
    for c in CUILS:
        assert rules.problema_cuil(c) == ref_validation.problema_cuil(c), c
        for e in EMAILS:
            assert rules.problema_alta_docente(c, e) == ref_validation.problema_alta_docente(c, e)
    for a in CUILS:
        for b in CUILS:
            for e1 in EMAILS[:6]:
                for e2 in EMAILS[:6]:
                    assert rules.problema_edicion_docente(a, b, e1, e2) == \
                        ref_validation.problema_edicion_docente(a, b, e1, e2), (a, b, e1, e2)


def test_identity_helpers_equivalent():
    values = CUILS + ["Pérez, Ana", "  Ana  María  Pérez ", "Pérez", float("nan"), 20123456789.0, "nat", "NaN"]
    for v in values:
        assert rules.limpiar_texto_tabla(v) == ref_texto.limpiar_texto_tabla(v)
        assert rules.normalizar_clave(v) == ref_texto.normalizar_clave(v)
        assert rules.clave_cuil(v) == ref_identidad._clave_cuil(v)
        assert rules.limpiar_cuil(v) == ref_identidad.limpiar_cuil(v)
        assert rules.separar_docente_en_apellido_nombres(v) == ref_identidad.separar_docente_en_apellido_nombres(v)
    for ap in ["", None, " Pérez ", "Gómez"]:
        for no in ["", None, " Ana ", "Luis"]:
            assert rules.nombre_completo(ap, no) == ref_identidad.nombre_completo(ap, no)


def test_b12a_posgrado_equivalent():
    values = ["", None, float("nan"), "Doctor", "doctora", " DOCTORADO ", "Magíster", "magister", "Maestría", "master",
              "Especialista", "especialización", "Licenciado", "  ", "Dr.", "MAGÍSTER"]
    for v in values:
        assert rules.canonical_posgrado_level(v) == ref_b12a.canonical_posgrado_level(v), v
        assert rules.nivel_posgrado_salarial_normalizado(v) == ref_b12a.nivel_posgrado_salarial_normalizado(v)
        try:
            expected = ref_b12a.require_posgrado_level_for_write(v)
        except ref_b12a.PosgradoNivelInvalido as exc:
            with pytest.raises(rules.PosgradoNivelInvalido) as got:
                rules.require_posgrado_level_for_write(v)
            assert str(got.value) == str(exc)
        else:
            assert rules.require_posgrado_level_for_write(v) == expected


def test_catalogs_equivalent():
    from deptit_refactor.catalogs.designaciones import ESTADOS_DOCENTE
    from deptit_refactor.catalogs.salarios import ADICIONAL_POSGRADO_V256

    assert rules.ESTADOS_DOCENTE == list(ESTADOS_DOCENTE)
    assert rules.NIVELES_POSGRADO_SALARIAL == list(ADICIONAL_POSGRADO_V256)
    text = ENTRY.read_text(encoding="utf-8")
    assert 'TIPOS_DOCENTE = ["Propio", "Prestado"]' in text
    assert 'NIVELES_POSGRADO_SALARIAL_V256 = ["", "Especialista", "Magíster", "Doctor"]' in text
    assert 'estados_baja_docente = ["Renunciado", "Jubilado", "Fallecido"]' in text


def test_text_filter_equivalent():
    from deptit_refactor.common.text import filtrar_dataframe_por_texto

    df = pd.DataFrame([{"nombre_completo": "Pérez, Ana", "cuil": "20-1", "legajo": None, "email": "a@b.com"},
                       {"nombre_completo": "GOMEZ, Luis  María", "cuil": "27-2", "legajo": "15", "email": ""}])
    rows = df.to_dict(orient="records")
    cols = ["nombre_completo", "cuil", "legajo", "titulo", "email"]
    for q in ["", "pérez", "PEREZ", "luis maría", "luis  maría", "27", "15", "@", "zzz", None, "  ana "]:
        expected = filtrar_dataframe_por_texto(df, q, cols).to_dict(orient="records")
        got = rules.filtrar_por_texto(rows, q, cols)
        assert json.dumps(got, default=str) == json.dumps(expected, default=str), q


# ------------------------------------------------------------------------------------------------ carga rapida
PASTES = [
    "CUIL\tApellido\tNombres\tLegajo\tEstado\n20-12345678-9\tPérez\tAna\t00123\t\n27-1 2345678-3\tGómez\tLuis\t\tLicencia\n",
    "cuil;docente;email\n20123456789;Ana María Pérez;a@b.com\n20123456789.0;Pérez, Ana;\n;Sin cuil;\n",
    "20-12345678-9\tPérez\tAna\t15\tLic.\n27-12345678-3\tGómez\tLuis\t16\tProf.\n",
    "Apellido y nombre,CUIT,Correo electrónico,Teléfono,Observación\n\"Pérez, Ana\",20-12345678-9,a@b.com,011,obs\n",
    "", "   \n  ",
]


@pytest.mark.parametrize("texto", PASTES)
def test_paste_parser_equivalent(db_conn, texto):
    ns = certified_docentes(db_conn, 1, 1)
    expected = ns["parsear_docentes_pegados"](texto)
    got = carga.parsear_docentes_pegados(texto)
    assert got.equals(expected) or (got.empty and expected.empty)
    assert carga.filas_pegadas(texto) == ([] if expected.empty else
                                          [{c: str(r[c]) for c in carga.COLUMNAS} for _, r in expected.iterrows()])


def test_excel_model_equivalent(db_conn):
    ns = certified_docentes(db_conn, 1, 1)
    expected = load_workbook(io.BytesIO(ns["generar_excel_modelo_carga_rapida_docentes"](filas_modelo=1000)))
    got = load_workbook(io.BytesIO(carga.generar_excel_modelo_carga_rapida_docentes(filas_modelo=1000)))
    assert got.sheetnames == expected.sheetnames == ["Carga rápida", "Instrucciones", "Listas"]
    for name in got.sheetnames:
        a, b = got[name], expected[name]
        assert a.sheet_state == b.sheet_state and a.max_row == b.max_row and a.max_column == b.max_column
        for ra, rb in zip(a.iter_rows(), b.iter_rows()):
            for ca, cb in zip(ra, rb):
                assert (ca.value, ca.number_format, ca.fill.fgColor.rgb, ca.font.b) == \
                       (cb.value, cb.number_format, cb.fill.fgColor.rgb, cb.font.b)
        assert [(t.name, t.ref) for t in a.tables.values()] == [(t.name, t.ref) for t in b.tables.values()]
        assert [(d.formula1, str(d.sqref)) for d in a.data_validations.dataValidation] == \
               [(d.formula1, str(d.sqref)) for d in b.data_validations.dataValidation]
    assert list(got.defined_names) == list(expected.defined_names)
    assert got["Carga rápida"]["A1"].comment.text == expected["Carga rápida"]["A1"].comment.text


# ------------------------------------------------------------------------------------------------ base maestra
def test_base_maestra_equivalent_for_every_real_department(db_conn, docentes):
    deps = departments_with_docentes(db_conn)
    assert len(deps) >= 5
    total = 0
    for inst, dep in deps:
        ns = certified_docentes(db_conn, inst, dep)
        expected = records(ns["get_docentes"]())
        repo = DocentesRepository(db_conn, inst, dep)
        got = docentes._base_maestra(repo)
        assert got["historico"] is False  # ningun departamento real tiene hoy un periodo historico abierto
        rows = [{k: v for k, v in r.items() if k != "huella"} for r in got["docentes"]]
        assert len(rows) == len(expected), (inst, dep)
        for g, e in zip(rows, expected):
            assert g == {k: e.get(k) for k in g}, (inst, dep, g.get("cuil"))
        total += len(rows)
    assert total == db_conn.execute("SELECT count(*) FROM docentes").fetchone()[0]


def test_docente_existe_and_other_departments_equivalent(db_conn):
    deps = departments_with_docentes(db_conn)
    sample = [r[0] for r in db_conn.execute(
        "SELECT cuil FROM docentes WHERE regexp_replace(cuil,'[^0-9]','','g') IN (SELECT regexp_replace(cuil,'[^0-9]',"
        "'','g') FROM docentes GROUP BY 1 HAVING count(DISTINCT departamento_id) > 1) ORDER BY id LIMIT 6").fetchall()]
    sample += [r[0] for r in db_conn.execute("SELECT cuil FROM docentes ORDER BY id DESC LIMIT 4").fetchall()]
    sample += ["", "20-00000000-0"]
    for inst, dep in deps:
        ns = certified_docentes(db_conn, inst, dep)
        repo = DocentesRepository(db_conn, inst, dep)
        assert records(ns["get_docentes_otros_departamentos_para_prestamo"]()) == \
            [{k: _norm(v) for k, v in r.items()} for r in repo.prestables()]
        for cuil in sample:
            exp = ns["docente_existe"](cuil)
            got = repo.docente_existe(rules.clave_cuil(cuil))
            assert (got is None) == exp.empty
            if got is not None:
                assert {k: _norm(v) for k, v in got.items()} == records(exp)[0]
            exp_otros = ns["get_docentes_mismo_cuil_otro_departamento"](rules.limpiar_cuil(cuil))
            got_otros = repo.mismo_cuil_otro_departamento(rules.clave_cuil(rules.limpiar_cuil(cuil))) \
                if str(rules.limpiar_cuil(cuil)).strip() else []
            assert [{k: _norm(v) for k, v in r.items()} for r in got_otros] == records(exp_otros)


def test_cuiles_huerfanos_equivalent(db_conn):
    for inst, dep in departments_with_docentes(db_conn):
        ns = certified_docentes(db_conn, inst, dep)
        exp = ns["get_cuiles_huerfanos_v168"](inst, dep)
        got = identidad.cuiles_huerfanos(DocentesRepository(db_conn, inst, dep))
        assert [(g["cuil_huerfano"], g["referencias"], g["detalle"]) for g in got] == \
            [(r["CUIL huérfano"], int(r["Referencias"]), r["Detalle"]) for _, r in exp.iterrows()]
