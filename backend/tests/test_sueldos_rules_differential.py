"""Diferenciales del MOTOR puro de Sueldos: ``sueldos.rules`` vs las funciones certificadas ejecutadas desde el entry
(``certified_sueldos``, B12A re-enlazado).  Producto de cargos, dedicaciones, Ad Honorem, antiguedad, posgrado y escalas
(incluidos cargo inexistente, texto no exacto, dedicacion desconocida/legacy, NULL/NaN, tipos raros); igualdad EXACTA
(``==`` de floats: mismos ``round`` en el mismo orden, H8).  Referencia B12A: 3.273.612,85."""

from __future__ import annotations

import itertools
import math
from datetime import date

import pandas as pd
import pytest

from sueldos import rules as SR
from sueldos_support import certified_sueldos, db_conn  # noqa: F401  (fixture)

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")

ESCALA = dict(SR.BASICOS_JUNIO_2026_V256)
ESCALAS = [ESCALA, {}, None, {"Titular": 487144.77, "JTP": "326359.56", "Adjunto": None, "ZZNEXT": 1.005},
           {"Titular": 100.005, "Ayudante 2da": 0.015, "Asociado": 999999.995}]
CARGOS = SR.CARGOS + ["", None, "Adjunto ", "Profesor Adjunto", "titular", "ZZNEXT"]
DEDICACIONES = list(SR.MULTIPLICADOR_DEDICACION_V256) + ["Simple Ad Honorem", "semiexclusiva", " Exclusiva  +  Simple ",
                                                         "", None, "x", "PARCIAL"]
ADH = ["Sí", "No", "SI", "si", "1", "true", "Verdadero", "yes", "", None, "Si ", "no", "S"]
ANTIG = [None, float("nan"), 0, 4, 5, 6, 7, 9, 10, 11, 12, 14, 15, 16, 17, 19, 20, 21, 22, 23, 24, 80, -3, 4.9,
         "12", "x", "  7 "]
NIVELES = ["", None, float("nan"), "Doctor", "doctora", "DOCTORADO", "Magíster", "magister", "Maestría", "master",
           "Especialista", "especialización", "PhD", "  doctor  "]


@pytest.fixture(scope="module")
def ns():
    import db
    import psycopg
    s = db.load_settings()
    db.check_config(s)
    conn = psycopg.connect(s["database_url"], connect_timeout=5, application_name="deptit_next_tests")
    try:
        db.verify_identity(conn)
        yield certified_sueldos(conn, 1, 1)
    finally:
        conn.rollback()
        conn.close()


def _eq(a, b):
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    return a == b and type(a) is type(b)


def test_referencia_b12a(ns):
    r = SR.calcular_sueldo_designacion_v256("Titular", "Exclusiva", "No", 10, "Doctor", ESCALA)
    assert r == ns["calcular_sueldo_designacion_v256"]("Titular", "Exclusiva", "No", 10, "Doctor", ESCALA)
    assert r["total_estimado"] == 3273612.85 and r["adicional_posgrado"] == 350744.23
    assert SR.moneda_v256(r["total_estimado"]) == "$ 3.273.612,85"


def test_motor_producto_completo(ns):
    cert = ns["calcular_sueldo_designacion_v256"]
    n = 0
    for escala in ESCALAS:
        for cargo, ded in itertools.product(CARGOS, DEDICACIONES):
            for adh, antig, nivel in [(a, b, c) for a in ADH[:4] for b in ANTIG[::3] for c in NIVELES[::2]]:
                a = SR.calcular_sueldo_designacion_v256(cargo, ded, adh, antig, nivel, escala)
                b = cert(cargo, ded, adh, antig, nivel, escala)
                assert a == b and all(type(a[k]) is type(b[k]) for k in a), (cargo, ded, adh, antig, nivel, escala)
                n += 1
    assert n > 10000


@pytest.mark.parametrize("fn,cert,valores", [
    ("porcentaje_antiguedad_v256", "porcentaje_antiguedad_v256", ANTIG),
    ("antiguedad_entera_v256", "_antiguedad_entera_v256", ANTIG),
    ("porcentaje_posgrado_v256", "porcentaje_posgrado_v256", NIVELES),
    ("nivel_posgrado_v256", "_nivel_posgrado_salarial_normalizado_v256", NIVELES),
    ("multiplicador_dedicacion_v256", "multiplicador_dedicacion_v256", DEDICACIONES),
    ("es_ad_honorem_v162", "_es_ad_honorem_v162", ADH),
    ("estado_designacion_visible_v162", "_estado_designacion_visible_v162",
     ["Suspendida", "suspendida", "Activa", None, "", "Finalizada", " SUSPENDIDA "]),
    ("moneda_v256", "_moneda_v256", [0, None, 1234.5, 1234567.891, -12.345, "x", "1500", float("nan"), 0.005, 1e9]),
    ("etiqueta_mes_v256", "_etiqueta_mes_v256", ["2026-06", "2026-6", "x", None, "", "2026-06-01", "1999-12"]),
])
def test_funciones_puras(ns, fn, cert, valores):
    for v in valores:
        assert _eq(getattr(SR, fn)(v), ns[cert](v)), (fn, v)


def test_meses_ejecucion_v258(ns):
    fechas = [None, "", "2026-01-01", "2026-12-31", "31/12/2026", date(2026, 3, 1), "2027-12-31", "2026-01-15",
              "2025-12-31", "x", pd.Timestamp("2026-08-01")]
    for a, b in itertools.product(fechas, fechas):
        assert SR.meses_ejecucion_v258(a, b) == ns["_meses_ejecucion_proyecto_v258"](a, b), (a, b)


def test_mes_ref_v256(ns):
    hoy = date(2026, 10, 26)  # FIXED_TODAY del namespace certificado
    for v in [None, "2026-07-31", "31/07/2026", "", "x", date(2025, 1, 5), pd.Timestamp("2026-02-01"), float("nan")]:
        assert SR.mes_ref_v256(v, hoy) == ns["_mes_ref_v256"](v), v


def test_escala_aplicable_sobre_filas_sinteticas(ns):
    df = pd.DataFrame([
        {"mes_referencia": m, "cargo": c, "basico_simple": v}
        for m, extra in [("2025-12", 1.0), ("2026-06", 2.0), ("2026-09", 3.0), ("2027-02", 4.0)]
        for c, v in [(c, b * extra) for c, b in ESCALA.items()]
    ] + [{"mes_referencia": "2026-09", "cargo": "ZZNEXT", "basico_simple": 1.0},
         {"mes_referencia": "2026-09", "cargo": "  ", "basico_simple": 5.0},
         {"mes_referencia": "2026-11", "cargo": "Titular", "basico_simple": None}])
    hoy = date(2026, 10, 26)
    for objetivo in [None, "", "2025-11", "2025-12", "2026-01", "2026-06", "2026-08", "2026-09", "2026-10", "2026-11",
                     "2027-02", "2099-12", "2026-9", "x"]:
        a = SR.escala_aplicable_v256(df, objetivo, hoy)
        ns["get_escalas_salariales_v256"] = lambda: df
        b = ns["obtener_escala_aplicable_v256"](objetivo)
        assert a == b, objetivo
        assert SR.escala_salarial_mes_v256(df, objetivo) == ns["get_escala_salarial_mes_v256"](objetivo)
    assert SR.escala_aplicable_v256(pd.DataFrame(columns=["mes_referencia", "cargo", "basico_simple"]), "2026-10",
                                    hoy) == (None, {})


def test_tabla_salarial_pestana_2(ns):
    """Transcripcion de l. 61845-61851 con las funciones certificadas vs ``tabla_salarial_v256``."""
    cert = ns["calcular_sueldo_designacion_v256"]
    for escala in (ESCALA, {"Titular": 1.0}, {}):
        for ded in SR.DEDICACIONES_TABLA:
            for nivel in SR.NIVELES_POSGRADO_SALARIAL_V256:
                esperado = []
                for cargo in ns["CARGOS"]:
                    fila = {"Cargo": cargo, "Básico Simple": ns["_moneda_v256"](escala.get(cargo, 0))}
                    for etiqueta, anios in [("0–4", 0), ("5–6", 5), ("7–9", 7), ("10–11", 10), ("12–14", 12),
                                            ("15–16", 15), ("17–19", 17), ("20–21", 20), ("22–23", 22), ("24+", 24)]:
                        fila[f"{etiqueta} años"] = ns["_moneda_v256"](cert(cargo, ded, "No", anios, nivel, escala)[
                            "total_estimado"])
                    esperado.append(fila)
                assert SR.tabla_salarial_v256(escala, ded, nivel) == esperado


def test_catalogos_identicos_al_certificado(ns):
    assert SR.ADICIONAL_POSGRADO_V256 == ns["ADICIONAL_POSGRADO_V256"]
    assert list(SR.MULTIPLICADOR_DEDICACION_V256.items()) == list(ns["MULTIPLICADOR_DEDICACION_V256"].items())
    assert SR.BASICOS_JUNIO_2026_V256 == ns["BASICOS_JUNIO_2026_V256"]
    assert SR.NIVELES_POSGRADO_SALARIAL_V256 == ns["NIVELES_POSGRADO_SALARIAL_V256"]
    assert SR.CARGOS == ns["CARGOS"] and SR.HORAS_POR_DEDICACION == ns["HORAS_POR_DEDICACION"]


def test_formulario_valor_inicial(ns):
    """``number_input`` de "⚙️ Escalas básicas": mes -> aplicable anterior -> 06/2026 -> 0."""
    for escala_mes, previa in [({}, {}), ({"Titular": 5.555}, {}), ({}, {"JTP": 7.0}), ({"JTP": 0}, {"JTP": 9.0})]:
        for cargo in SR.CARGOS:
            esperado = round(float(escala_mes.get(cargo, previa.get(cargo, ns["BASICOS_JUNIO_2026_V256"].get(
                cargo, 0.0))) or 0.0), 2)
            assert SR.valor_inicial_formulario(cargo, escala_mes, previa) == esperado
