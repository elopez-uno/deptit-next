"""fix-horas-en-resumen-docente — Bugs A y B del Resumen docente (``integraciones.resumen_horas``).

Tests funcionales SIN base de datos: designaciones y movimientos sintéticos con la forma exacta de las lecturas
institucionales del motor (``_get_designaciones_periodo_institucional_v149`` /
``_get_movimientos_periodo_institucional_v149``) y la tarjeta real de ``integraciones.resumen_pagina`` sobre un namespace simulado.  Los CUIL y nombres son ficticios;
los casos reproducen las situaciones reportadas (Rossi, Cetrangolo, Muñoz).

Regla: ``horas_base + variación_neta = horas_finales``; la variación incluye altas (+h), bajas (−h), aumentos y
disminuciones de dedicación.
"""
from __future__ import annotations

import pandas as pd
import pytest

from integraciones import resumen_horas as RH
from integraciones import resumen_pagina as RP

EXACTAS = (11, "Departamento de Ciencias Exactas y Naturales")
INFORMATICA = (12, "Departamento de Informática e Ingeniería")

P_2026_1_CERRADO = {"id": 1, "nombre": "2026-1", "fecha_inicio": "2026-01-01", "fecha_fin": "2026-07-31",
                    "estado": "Cerrado"}
P_2026_2_ABIERTO = {"id": 2, "nombre": "2026-2", "fecha_inicio": "2026-08-01", "fecha_fin": "2026-12-31",
                    "estado": "Abierto"}

_ids = iter(range(1000, 100000))


def des(dep, cargo="JTP", dedicacion="Simple", horas=10, tipo="Interino", estado="Activa",
        desde="2026-01-01", hasta="2026-07-31", prevista=None, efectiva=None, funcion=0, did=None) -> dict:
    """Fila con las columnas de ``_get_designaciones_periodo_institucional_v149``
    (``fecha_hasta_prevista`` = COALESCE(prevista, hasta), como en el SELECT del motor)."""
    return {"id": did if did is not None else next(_ids), "cuil": "20000000001", "periodo_id": 1,
            "departamento_id": dep[0], "departamento": dep[1], "periodo": "", "cargo": cargo,
            "dedicacion": dedicacion, "horas": horas, "tipo_designacion": tipo, "estado": estado,
            "fecha_desde": desde, "fecha_hasta": hasta, "fecha_hasta_prevista": prevista or hasta,
            "fecha_finalizacion_efectiva": efectiva, "fecha_registro_finalizacion": None,
            "motivo_finalizacion": "", "observaciones": "", "funcion_no_docente": funcion,
            "texto_funcion_no_docente": ""}


def mov(dep, tipo, variacion=0.0, detalle="", fecha="2026-09-10") -> dict:
    """Fila con las columnas de ``_get_movimientos_periodo_institucional_v149``."""
    return {"id": next(_ids), "fecha": fecha, "tipo_movimiento": tipo, "detalle": detalle,
            "horas_variacion": variacion, "departamento_id": dep[0] if dep else None,
            "departamento": dep[1] if dep else "Sin departamento"}


def calc(filas, movs=(), periodo=P_2026_2_ABIERTO, **kw):
    return RH.calcular(pd.DataFrame(filas), pd.DataFrame(list(movs)), periodo, **kw)


def terna(r) -> tuple:
    return r["horas_base"], r["variacion_neta"], r["horas_finales"]


# ===================================================================================== Bug A: institucional
def rossi_2026_1() -> list[dict]:
    # Cierre técnico: ambas Finalizada SIN fecha efectiva (no es una baja).
    return [des(EXACTAS, "Ayudante 1ra", estado="Finalizada"),
            des(INFORMATICA, "Ayudante 1ra", estado="Finalizada")]


def cetrangolo_2026_1() -> list[dict]:
    return [des(EXACTAS, "JTP", tipo="Concursado", estado="Finalizada", desde="2025-03-01", hasta="2030-02-28"),
            des(EXACTAS, "JTP", tipo="Interino", estado="Finalizada"),
            des(INFORMATICA, "JTP", tipo="Interino", estado="Finalizada")]


def test_rossi_2026_1_compartido_20_hs():
    r = calc(rossi_2026_1(), periodo=P_2026_1_CERRADO)
    assert r["compartido"] is True
    assert r["horas_finales"] == 20
    assert [(d["departamento"], d["horas"]) for d in r["departamentos"]] == [(EXACTAS[1], 10), (INFORMATICA[1], 10)]
    assert terna(r) == (20, 0, 20)
    assert r["baja_en_periodo"] is False and r["lectura_historica"] is True


def test_cargos_identicos_en_departamentos_distintos_no_se_fusionan():
    """Regresión del Bug A: la clave legada (cargo, dedicación, tipo, horas) sin departamento fusionaba estas filas."""
    filas = RH.preparar_designaciones(pd.DataFrame(rossi_2026_1()))
    assert len(filas) == 2 and {f["_dep_id"] for f in filas} == {EXACTAS[0], INFORMATICA[0]}


def test_cetrangolo_2026_1_compartido_30_hs():
    r = calc(cetrangolo_2026_1(), periodo=P_2026_1_CERRADO)
    assert r["compartido"] is True
    assert r["horas_finales"] == 30
    por_dep = {d["departamento"]: d for d in r["departamentos"]}
    assert por_dep[EXACTAS[1]]["horas"] == 20 and por_dep[INFORMATICA[1]]["horas"] == 10
    assert "JTP (Concursado) · Simple · 10 hs" in por_dep[EXACTAS[1]]["cargo/s en el período"]
    assert "JTP (Interino) · Simple · 10 hs" in por_dep[EXACTAS[1]]["cargo/s en el período"]
    assert terna(r) == (30, 0, 30)


def test_rossi_2026_2_abierto_sigue_compartido():
    filas = [des(EXACTAS, "Ayudante 1ra", desde="2026-08-01", hasta="2026-12-31"),
             des(INFORMATICA, "Ayudante 1ra", desde="2026-08-01", hasta="2026-12-31")]
    r = calc(filas, periodo=P_2026_2_ABIERTO)
    assert r["compartido"] is True and terna(r) == (20, 0, 20) and r["lectura_historica"] is False


def test_un_solo_departamento_no_es_compartido():
    r = calc([des(EXACTAS, desde="2026-08-01", hasta="2026-12-31", horas=20)])
    assert r["compartido"] is False and r["cargos"] == [f"{EXACTAS[1]}: JTP (Interino) · Simple · 20 hs"]


def test_no_docentes_y_suspendidas_no_suman_horas():
    filas = [des(EXACTAS, desde="2026-08-01", hasta="2026-12-31", horas=20),
             des(EXACTAS, "Ayudante 1ra", desde="2026-08-01", hasta="2026-12-31", funcion=1),
             des(INFORMATICA, "JTP", desde="2026-08-01", hasta="2026-12-31", estado="Suspendida")]
    r = calc(filas)
    assert terna(r) == (20, 0, 20) and r["compartido"] is False
    assert r["suspendidas"] == [f"{INFORMATICA[1]}: JTP · (Interino) · Simple · Suspendida (licenciada)"]


def test_departamento_sombra_no_se_mezcla():
    """Regla v227: otro departamento_id con el MISMO nombre visible que el actual no pertenece al tenant."""
    sombra = (99, EXACTAS[1])
    filas = [des(EXACTAS, desde="2026-08-01", hasta="2026-12-31"),
             des(sombra, desde="2026-08-01", hasta="2026-12-31")]
    r = calc(filas, dep_actual_id=EXACTAS[0], dep_actual_nombre=EXACTAS[1])
    assert terna(r) == (10, 0, 10) and r["compartido"] is False


def test_cerrado_no_confunde_vencimiento_dentro_del_periodo_con_vigencia():
    """En un período cerrado la foto final es por fechas: una interina vencida antes del fin es una baja real."""
    filas = [des(EXACTAS, estado="Finalizada"), des(INFORMATICA, estado="Finalizada", hasta="2026-05-31")]
    r = calc(filas, periodo=P_2026_1_CERRADO)
    assert terna(r) == (20, -10, 10)
    assert r["compartido"] is True  # tuvo designaciones en 2 departamentos durante el período
    assert {d["departamento"]: d["horas"] for d in r["departamentos"]} == {EXACTAS[1]: 10, INFORMATICA[1]: 0}


# ===================================================================================== Bug B: evolución
def test_munoz_baja_40_en_periodo_abierto():
    filas = [des(EXACTAS, "JTP", "Exclusiva", 40, desde="2026-08-01", hasta="2026-12-31", estado="Finalizada",
                 efectiva="2026-09-15")]
    r = calc(filas, [mov(EXACTAS, "Baja de designación", -40, fecha="2026-09-15")])
    assert terna(r) == (40, -40, 0)
    assert r["baja_en_periodo"] is True and r["cargos"] == []


def test_munoz_baja_40_tras_cerrar_el_periodo():
    """La baja deja fecha_hasta intacta y solo carga la fecha efectiva: el histórico no debe volver a mostrar 40 hs."""
    filas = [des(EXACTAS, "JTP", "Exclusiva", 40, desde="2026-08-01", hasta="2026-12-31", estado="Finalizada",
                 efectiva="2026-09-15")]
    cerrado = dict(P_2026_2_ABIERTO, estado="Cerrado")
    r = calc(filas, [mov(EXACTAS, "Baja de designación", -40)], periodo=cerrado)
    assert terna(r) == (40, -40, 0) and r["baja_en_periodo"] is True


def test_alta_de_20():
    r = calc([des(EXACTAS, horas=20, desde="2026-09-01", hasta="2026-12-31")],
             [mov(EXACTAS, "Alta de designación", 20)])
    assert terna(r) == (0, 20, 20)
    assert "variacion_dedicacion" not in r  # un único concepto de variación: la neta


def test_aumento_10_a_20():
    """El cambio de dedicación edita la fila: la base se recupera descontando el movimiento."""
    r = calc([des(EXACTAS, dedicacion="Semi", horas=20, desde="2026-08-01", hasta="2026-12-31")],
             [mov(EXACTAS, "Aumento de dedicación", 10)])
    assert terna(r) == (10, 10, 20)


def test_aumento_sin_horas_variacion_usa_antes_ahora():
    detalle = ("2026-2 - Antes: JTP - Simple - 10 hs - Interino - Ad Honorem: No / "
               "Ahora: JTP - Semi - 20 hs - Interino - Ad Honorem: No")
    r = calc([des(EXACTAS, dedicacion="Semi", horas=20, desde="2026-08-01", hasta="2026-12-31")],
             [mov(EXACTAS, "Aumento de dedicación", 0, detalle=detalle)])
    assert terna(r) == (10, 10, 20)


def test_disminucion_40_a_20():
    r = calc([des(EXACTAS, dedicacion="Semi", horas=20, desde="2026-08-01", hasta="2026-12-31")],
             [mov(EXACTAS, "Disminución de dedicación", -20)])
    assert terna(r) == (40, -20, 20)


def test_sin_movimientos():
    r = calc([des(EXACTAS, horas=20, desde="2026-08-01", hasta="2026-12-31")])
    assert terna(r) == (20, 0, 20)


def test_varios_movimientos_variacion_neta():
    filas = [
        des(EXACTAS, "JTP", "Semi", 20, desde="2026-08-01", hasta="2026-12-31"),        # 10 -> 20 (+10)
        des(INFORMATICA, "Ayudante 1ra", horas=10, desde="2026-10-01", hasta="2026-12-31"),  # alta (+10)
        des(EXACTAS, "Adjunto", "Exclusiva", 40, desde="2026-08-01", hasta="2026-12-31",
            estado="Finalizada", efectiva="2026-11-01"),                               # baja (-40)
    ]
    movs = [mov(EXACTAS, "Aumento de dedicación", 10), mov(INFORMATICA, "Alta de designación", 10),
            mov(EXACTAS, "Baja de designación", -40)]
    r = calc(filas, movs)
    assert terna(r) == (50, -20, 30)  # 50 + 10 + 10 - 40 = 30


def test_alta_y_aumento_en_el_mismo_periodo_no_da_base_negativa():
    r = calc([des(EXACTAS, horas=20, desde="2026-09-01", hasta="2026-12-31")],
             [mov(EXACTAS, "Aumento de dedicación", 10)])
    assert terna(r) == (0, 20, 20)


def test_movimientos_de_departamento_ajeno_se_ignoran():
    r = calc([des(EXACTAS, horas=20, desde="2026-08-01", hasta="2026-12-31")],
             [mov((77, "Otro"), "Aumento de dedicación", 10)])
    assert terna(r) == (20, 0, 20)


CASOS = {
    "rossi": (rossi_2026_1, (), P_2026_1_CERRADO),
    "cetrangolo": (cetrangolo_2026_1, (), P_2026_1_CERRADO),
    "baja": (lambda: [des(EXACTAS, horas=40, desde="2026-08-01", hasta="2026-12-31", estado="Finalizada",
                          efectiva="2026-09-15")], (), P_2026_2_ABIERTO),
    "alta": (lambda: [des(EXACTAS, horas=20, desde="2026-09-01", hasta="2026-12-31")], (), P_2026_2_ABIERTO),
    "aumento": (lambda: [des(EXACTAS, horas=20, desde="2026-08-01", hasta="2026-12-31")],
                (("Aumento de dedicación", 10),), P_2026_2_ABIERTO),
    "disminucion": (lambda: [des(EXACTAS, horas=20, desde="2026-08-01", hasta="2026-12-31")],
                    (("Disminución de dedicación", -20),), P_2026_2_ABIERTO),
    "vacio": (lambda: [], (), P_2026_2_ABIERTO),
}


@pytest.mark.parametrize("caso", sorted(CASOS))
def test_invariante_base_mas_variacion_igual_final(caso):
    filas, movs, periodo = CASOS[caso]
    r = calc(filas(), [mov(EXACTAS, t, v) for t, v in movs], periodo=periodo)
    assert r["horas_base"] + r["variacion_neta"] == pytest.approx(r["horas_finales"])
    assert r["horas_base"] >= 0 and r["horas_finales"] >= 0
    assert r["horas_finales"] == pytest.approx(sum(d["horas"] for d in r["departamentos"]))


# ===================================================================================== tarjeta (resumen_pagina)
def motor_bug(horas=10.0, historica=True, deptos=None, **extra) -> dict:
    """Resumen del motor certificado TAL COMO LO DEVUELVE HOY en los casos reportados (Bug A/B)."""
    d = {"cargos_actuales": ["Ayudante 1ra (Interino) · Simple · 10 hs"], "horas_actuales": horas,
         "horas_inicio": horas, "variacion_horas": 0.0,
         "cambios_cargo": ["Sin cambio de cargo registrado en este período."],
         "estado_resumen_periodo": "", "baja_en_periodo": False, "lectura_historica": historica,
         "departamentos_periodo": deptos if deptos is not None else [
             {"departamento": EXACTAS[1], "cargo/s en el período": "Ayudante 1ra (Interino) · Simple · 10 hs",
              "horas": horas}],
         "balance_horas_periodo": {"horas_inicio_operativo": horas, "variacion_operativa": 0.0,
                                   "horas_resultado_operativo": horas},
         "sin_designacion_local_periodo_v227": False, "funciones_no_docentes": []}
    d.update(extra)
    return d


def fake_ns(filas, movs=(), motor=None, prestado=False, pg=True, dep_actual=INFORMATICA) -> dict:
    df = pd.DataFrame(filas)
    return {
        "USE_POSTGRESQL": pg,
        "get_resumen_actual_periodo_docente": lambda cuil, pid: dict(motor or motor_bug()),
        "es_docente_prestado_local": lambda cuil: prestado,
        "limpiar_texto_tabla": lambda v: "" if v is None or (isinstance(v, float) and pd.isna(v)) else " ".join(
            str(v).split()),
        "_get_designaciones_periodo_institucional_v149": lambda cuil, pid: df.copy(),
        "_get_movimientos_periodo_institucional_v149": lambda cuil, pid: pd.DataFrame(list(movs)),
        "_pg_current_dep_id": lambda: dep_actual[0],
        "_nombre_departamento_actual_v227": lambda: dep_actual[1],
        # Misma fuente que la sección "Designaciones institucionales del docente" (wrapper v162 del motor).
        "get_designaciones_docente_todos_departamentos_pg": lambda cuil, pid: df.copy(),
    }


def tarjeta(ns, periodo):
    return RP.tarjeta(ns, "20-00000000-1", periodo["id"], periodo["nombre"], periodo)


def test_tarjeta_rossi_2026_1_historica_compartida():
    t = tarjeta(fake_ns(rossi_2026_1()), P_2026_1_CERRADO)
    assert t["titulo"] == "Resumen histórico del período — 2026-1"
    assert t["horas"] == {"label": "Horas totales del período", "valor": "20 hs"}
    assert t["compartido"] and "DOCENTE COMPARTIDO" in t["compartido"]
    assert t["cargos"]["label"] == "Cargo/s por departamento" and len(t["cargos"]["lineas"]) == 2
    assert t["departamentos"]["filas"] == [[EXACTAS[1], "Ayudante 1ra (Interino) · Simple · 10 hs", 10.0],
                                           [INFORMATICA[1], "Ayudante 1ra (Interino) · Simple · 10 hs", 10.0]]
    e = t["evolucion"]
    assert (e["base"]["valor"], e["movimiento"]["valor"], e["resultado"]["valor"]) == ("20 hs", "0 hs", "20 hs")


def test_tarjeta_cetrangolo_2026_1_30_hs():
    t = tarjeta(fake_ns(cetrangolo_2026_1()), P_2026_1_CERRADO)
    assert t["horas"]["valor"] == "30 hs" and t["compartido"]
    assert {f[0]: f[2] for f in t["departamentos"]["filas"]} == {EXACTAS[1]: 20.0, INFORMATICA[1]: 10.0}


def test_tarjeta_munoz_baja_40():
    filas = [des(EXACTAS, "JTP", "Exclusiva", 40, desde="2026-08-01", hasta="2026-12-31", estado="Finalizada",
                 efectiva="2026-09-15")]
    motor = motor_bug(horas=0.0, historica=False, deptos=[], baja_en_periodo=True)
    t = tarjeta(fake_ns(filas, [mov(EXACTAS, "Baja de designación", -40)], motor, dep_actual=EXACTAS),
                P_2026_2_ABIERTO)
    assert t["cargos"]["lineas"] == ["Baja en el período"]
    assert t["horas"] == {"label": "Horas actuales", "valor": "0 hs"}
    e = t["evolucion"]
    assert (e["base"]["valor"], e["movimiento"]["valor"], e["resultado"]["valor"]) == ("40 hs", "-40 hs", "0 hs")
    assert e["movimiento"]["label"] == "Baja en el período" and e["movimiento"]["tono"] == "negativo"
    # Indicador superior = misma variación neta que la evolución (no "solo dedicación").
    assert t["variacion"] == {"label": "Aumento / disminución", "valor": "-40 hs", "tono": "negativo",
                              "caption": "Variación neta de horas en el período."}


TARJETA_CASOS = {
    # caso: (filas, movimientos, valor esperado del indicador "Aumento / disminución", tono)
    "alta_20": (lambda: [des(EXACTAS, horas=20, desde="2026-09-01", hasta="2026-12-31")],
                [("Alta de designación", 20)], "+20 hs", "positivo"),
    "aumento_10_a_20": (lambda: [des(EXACTAS, horas=20, desde="2026-08-01", hasta="2026-12-31")],
                        [("Aumento de dedicación", 10)], "+10 hs", "positivo"),
    "disminucion_40_a_20": (lambda: [des(EXACTAS, horas=20, desde="2026-08-01", hasta="2026-12-31")],
                            [("Disminución de dedicación", -20)], "-20 hs", "negativo"),
    "baja_40": (lambda: [des(EXACTAS, horas=40, desde="2026-08-01", hasta="2026-12-31", estado="Finalizada",
                             efectiva="2026-09-15")], [("Baja de designación", -40)], "-40 hs", "negativo"),
    "sin_cambios": (lambda: [des(EXACTAS, horas=20, desde="2026-08-01", hasta="2026-12-31")], [], "0 hs", "neutro"),
}


@pytest.mark.parametrize("caso", sorted(TARJETA_CASOS))
def test_indicador_superior_es_la_variacion_neta_de_la_evolucion(caso):
    filas, movs, valor, tono = TARJETA_CASOS[caso]
    t = tarjeta(fake_ns(filas(), [mov(EXACTAS, tp, v) for tp, v in movs], dep_actual=EXACTAS), P_2026_2_ABIERTO)
    assert t["variacion"]["valor"] == valor and t["variacion"]["tono"] == tono
    assert t["variacion"]["valor"] == t["evolucion"]["movimiento"]["valor"]
    assert t["variacion"]["tono"] == t["evolucion"]["movimiento"]["tono"]
    assert t["variacion"]["caption"] == "Variación neta de horas en el período."


def test_rossi_y_cetrangolo_indicador_superior_cero_coherente():
    for filas in (rossi_2026_1(), cetrangolo_2026_1()):
        t = tarjeta(fake_ns(filas), P_2026_1_CERRADO)
        assert t["variacion"]["valor"] == t["evolucion"]["movimiento"]["valor"] == "0 hs"


def test_tarjeta_igual_a_designaciones_institucionales():
    """Total y departamentos de la tarjeta = suma de la tabla "Designaciones institucionales del docente"."""
    ns = fake_ns(cetrangolo_2026_1())
    t = tarjeta(ns, P_2026_1_CERRADO)
    tabla = RP._seccion_tabla("Designaciones institucionales del docente — 2026-1",
                              ns["get_designaciones_docente_todos_departamentos_pg"]("x", 1), "vacío")["tabla"]
    cols = tabla["columnas"]
    por_dep: dict = {}
    for f in tabla["filas"]:
        dep = f[cols.index("departamento")]
        por_dep[dep] = por_dep.get(dep, 0) + float(f[cols.index("horas")])
    assert {f[0]: f[2] for f in t["departamentos"]["filas"]} == por_dep
    assert t["horas"]["valor"] == f"{sum(por_dep.values()):g} hs"


def test_tarjeta_prestado_sin_regresion():
    """Prestado: la designación es del departamento de origen; no se duplica en el receptor ni es compartido."""
    filas = [des(EXACTAS, "Adjunto", "Semi", 20, desde="2026-08-01", hasta="2026-12-31")]
    t = tarjeta(fake_ns(filas, prestado=True, dep_actual=INFORMATICA), P_2026_2_ABIERTO)
    assert t["aviso_prestado"].startswith(f"📌 DOCENTE PRESTADO: la designación sigue perteneciendo a {EXACTAS[1]}.")
    assert t["compartido"] is None
    assert t["caption_origen"] == "Designación/es consultada/s en el departamento de origen:"
    assert t["departamentos"]["filas"] == [[EXACTAS[1], "Adjunto (Interino) · Semi · 20 hs", 20.0]]
    assert t["horas"]["valor"] == "20 hs"


def test_tarjeta_propio_sin_designacion_local_conserva_regla_v227():
    """Docente propio sin fila local en el período: el motor deja la tarjeta vacía a propósito y no se reemplaza."""
    motor = motor_bug(horas=0.0, historica=False, deptos=[], cargos_actuales=[],
                      sin_designacion_local_periodo_v227=True)
    t = tarjeta(fake_ns([des(EXACTAS, desde="2026-08-01", hasta="2026-12-31")], motor=motor), P_2026_2_ABIERTO)
    assert t["horas"]["valor"] == "0 hs" and t["compartido"] is None


def test_tarjeta_sin_postgresql_conserva_el_motor():
    t = tarjeta(fake_ns(rossi_2026_1(), pg=False), P_2026_1_CERRADO)
    assert t["horas"]["valor"] == "10 hs"
    # Respaldo: valor del motor con su leyenda original (no se rotula como neta lo que no lo es).
    assert t["variacion"]["caption"] == "Solo cambios reales de dedicación."


def test_tarjeta_si_la_lectura_falla_conserva_el_motor():
    ns = fake_ns(rossi_2026_1())

    def falla(cuil, pid):
        raise RuntimeError("lectura")
    ns["_get_designaciones_periodo_institucional_v149"] = falla
    t = tarjeta(ns, P_2026_1_CERRADO)
    assert t["horas"]["valor"] == "10 hs"


def test_tarjeta_sin_fila_de_periodo_conserva_el_motor():
    t = RP.tarjeta(fake_ns(rossi_2026_1()), "20-00000000-1", 1, "2026-1")
    assert t["horas"]["valor"] == "10 hs"
