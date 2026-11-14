"""Diferenciales de Analisis — incluye Productividad: certificado (``reference_fix02``, ``certified_analisis``) vs motor
NEXT vendorizado (``analisis.motor``) y vs los contratos de pantalla (``analisis.pagina``), mismo estado.

Datos reales: departamentos 1, 2, 3, 4, 9 y 11, periodos abiertos e historicos (foto al cierre).  Casos sinteticos
``ZZNEXT`` (insertados en la transaccion del test, ROLLBACK): bordes de Productividad 39,5 / 40 / 49,9 / 50 / 60 /
60,5 / 100 / >100 %, 0 horas contratadas con actividad, sin actividad, extension, docente solo vs comision compartida
(regla del 50 %).  Se congelan las anomalias certificadas (D-AM13) para impedir "arreglos" accidentales.
"""

from __future__ import annotations

import io
import re
import zipfile

import pandas as pd
import psycopg
import pytest

from analisis import pagina as P
from analisis_support import (  # noqa: F401  (fixtures)
    certified_analisis, db_conn, escalares, igual_df, motor,
)

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")

INST = 1
CASOS = [(1, 9), (1, 5), (2, 11), (2, 1), (3, 10), (3, 4), (4, 13), (9, 14), (9, 3), (11, 6)]


def _comparar_metricas(c: dict, n: dict) -> None:
    assert escalares(c) == escalares(n)
    for k, v in c.items():
        if isinstance(v, pd.DataFrame):
            assert igual_df(v, n[k]), k


@pytest.mark.parametrize("dep,pid", CASOS)
def test_motor_igual_al_certificado(db_conn, dep, pid):
    """Metricas (14 capas), productividad v194, alertas, alumnos v248, grupos, comparacion v188, movimiento docente,
    periodo anterior equivalente, resumen ejecutivo y prompt: identicos al certificado."""
    c, n = certified_analisis(db_conn, INST, dep), motor(db_conn, INST, dep)
    mc, mn = c["get_metricas_analisis_periodo"](pid), n["get_metricas_analisis_periodo"](pid)
    _comparar_metricas(mc, mn)
    for nombre in ("get_docentes_productividad_periodo", "construir_alertas_periodo",
                   "get_analisis_alumnos_por_docente_grupos_v248"):
        assert igual_df(c[nombre](pid), n[nombre](pid)), nombre
    assert c["_alumnos_por_docente_periodo_v188"](pid, metricas=mc) == n["_alumnos_por_docente_periodo_v188"](pid, metricas=mn)
    assert c["_indicadores_comparacion_periodo_v188"](pid) == n["_indicadores_comparacion_periodo_v188"](pid)
    assert igual_df(P.movimientos_analisis(c, mc), P.movimientos_analisis(n, mn))
    fila = db_conn.execute("SELECT id, nombre, anio, semestre FROM periodos WHERE id=%s", [pid]).fetchone()
    per = {"id": fila[0], "nombre": fila[1], "anio": fila[2], "semestre": fila[3]}
    assert c["get_periodo_mismo_semestre_anio_anterior"](per) == n["get_periodo_mismo_semestre_anio_anterior"](per)
    prod, al = n["get_docentes_productividad_periodo"](pid), n["construir_alertas_periodo"](pid)
    assert c["generar_resumen_ejecutivo_automatico"](fila[1], mc, al, prod) == \
        n["generar_resumen_ejecutivo_automatico"](fila[1], mn, al, prod)
    assert c["construir_prompt_ia_periodo"](fila[1], mc, al, prod) == n["construir_prompt_ia_periodo"](fila[1], mn, al, prod)
    assert sum(len(o["commits"]) for o in c["_frames"].ops) == 0  # B12F: 0 escrituras al leer (D-AM2)


@pytest.mark.parametrize("dep,pid", [(1, 9), (1, 5), (9, 14), (3, 10)])
def test_contratos_de_pantalla_iguales(db_conn, dep, pid):
    """Las 5 pestañas (payload de UI) construidas sobre el certificado y sobre el motor NEXT son identicas."""
    c, n = certified_analisis(db_conn, INST, dep), motor(db_conn, INST, dep)
    out = []
    for ns in (c, n):
        per = P.periodos(ns)
        nombre = next(k for k, v in per["ids"].items() if v == pid)
        m = ns["get_metricas_analisis_periodo"](pid)
        alum = ns["_alumnos_por_docente_periodo_v188"](pid, metricas=m)
        es_hist = bool(m.get("lectura_historica_periodo"))
        mov = P.movimiento(ns, m, alum, pid, nombre, P.fila_periodo(per["df"], pid), es_hist)
        mov.pop("_df")
        auto = P.automatico(ns, m, pid, nombre)
        auto.pop("_alertas")
        op = P.comparacion_opciones(ns, per["df"], per["base"])
        cmp_ = P.comparacion(ns, per["df"], op, op["opciones"]) if op["opciones"] else None
        out.append({"periodos": {k: v for k, v in per.items() if k not in ("df", "base")},
                    "dashboard": P.dashboard(ns, m, alum, pid, nombre, es_hist), "plantel": P.plantel(ns, m, nombre, es_hist),
                    "movimiento": mov, "automatico": auto, "comparacion": cmp_})
    assert out[0] == out[1]


def _fechas_ficha(conn, ambito: bool) -> set:
    """Fechas posibles de "Inicio historico" / "Ultima alta" (dd/mm/aaaa) de los docentes del dep 1, calculadas con
    SQL independiente: con ``ambito`` restringidas al tenant de la sesion (NEXT), sin el, todos los tenants
    (B13-FIX02).  Incluye el ``fecha_alta`` propio (COALESCE certificado cuando no hay designaciones)."""
    filtro = " AND d.institucion_id = doc.institucion_id AND d.departamento_id = doc.departamento_id" if ambito else ""
    filas = conn.execute(
        f"SELECT (SELECT MIN(NULLIF(d.fecha_desde, '')) FROM designaciones d WHERE d.cuil = doc.cuil{filtro}), "
        f"(SELECT MAX(NULLIF(d.fecha_desde, '')) FROM designaciones d WHERE d.cuil = doc.cuil{filtro}), "
        "NULLIF(doc.fecha_alta, '') FROM docentes doc WHERE doc.institucion_id = %s AND doc.departamento_id = 1",
        [INST]).fetchall()
    return {f"{v[8:10]}/{v[5:7]}/{v[0:4]}" for fila in filas for v in fila if v}


def test_word_del_movimiento_docente_igual(db_conn):
    """Informe Word (python-docx): mismo contenido XML del documento que el certificado (D-AM11).

    Diferencia consciente de seguridad respecto de B13-FIX02: NEXT restringe las subconsultas al tenant de la sesion
    (``DQ-SCOPE-SUBQUERY-B12B``, Etapa 5 / Tanda A, aceptada por el usuario el 2026-11-02).  La ficha del docente
    (``get_resumen_docente`` base, entry l. 5004) calcula "Inicio historico" / "Ultima alta" con subconsultas por CUIL
    que en el certificado leen designaciones de OTROS departamentos/instituciones.  Solo esos dos valores pueden
    diferir, solo en docentes con designaciones en otro tenant, y el valor NEXT es el del tenant de la sesion; el resto
    del documento es identico byte a byte."""
    c, n = certified_analisis(db_conn, INST, 1), motor(db_conn, INST, 1)
    docs = []
    for ns in (c, n):
        df = P.movimientos_analisis(ns, ns["get_metricas_analisis_periodo"](9))
        data = ns["generar_informe_movimiento_docente_word_v175"]("2026-2", "Departamento ZZ", df, periodo_id=9)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            docs.append({k: z.read(k) for k in z.namelist() if k.startswith("word/") and k.endswith(".xml")})
    assert docs[0]["word/document.xml"]
    assert {k: v for k, v in docs[0].items() if k != "word/document.xml"} == \
        {k: v for k, v in docs[1].items() if k != "word/document.xml"}
    patron = re.compile(r"(<w:t[^>]*>)([^<]*)(</w:t>)")
    textos = [[m.group(2) for m in patron.finditer(d["word/document.xml"].decode("utf-8"))] for d in docs]
    assert len(textos[0]) == len(textos[1])
    distintos = [k for k, (a, b) in enumerate(zip(*textos)) if a != b]
    etiquetas = {"Inicio histórico", "Última alta"}
    assert all(k > 0 and textos[0][k - 1] in etiquetas for k in distintos)  # solo esos dos campos
    ajenos = db_conn.execute(
        "SELECT count(*) FROM docentes doc WHERE doc.institucion_id = %s AND doc.departamento_id = 1 AND EXISTS "
        "(SELECT 1 FROM designaciones d WHERE d.cuil = doc.cuil AND (d.institucion_id, d.departamento_id) <> "
        "(doc.institucion_id, doc.departamento_id))", [INST]).fetchone()[0]
    assert ajenos > 0 or not distintos
    certificadas, propias = _fechas_ficha(db_conn, False), _fechas_ficha(db_conn, True)
    assert all(textos[0][k] in certificadas and textos[1][k] in propias for k in distintos)
    enmascarar = lambda d: patron.sub(  # noqa: E731
        lambda m, it=iter(range(10 ** 6)): m.group(1) + ("#" if next(it) in distintos else m.group(2)) + m.group(3),
        d["word/document.xml"].decode("utf-8"))
    assert enmascarar(docs[0]) == enmascarar(docs[1])


# ------------------------------------------------------------------------------------------ casos sinteticos ZZNEXT
def _clonar(conn, tabla: str, donde: str, cambios: dict, params=()) -> int:
    cols = [r[0] for r in conn.execute("SELECT column_name FROM information_schema.columns WHERE table_name=%s AND "
                                       "column_name<>'id' ORDER BY ordinal_position", [tabla])]
    sel = ", ".join(f"%s AS {c}" if c in cambios else c for c in cols)
    valores = [cambios[c] for c in cols if c in cambios]
    return conn.execute(f"INSERT INTO {tabla} ({', '.join(cols)}) SELECT {sel} FROM {tabla} WHERE {donde} LIMIT 1 "
                        f"RETURNING id", valores + list(params)).fetchone()[0]


def _docente(conn, n: int, dedicacion="Simple", horas=10) -> str:
    cuil = f"20-99{n:06d}-1"
    _clonar(conn, "docentes", "institucion_id=1 AND departamento_id=1",
            {"cuil": cuil, "apellido": f"ZZNEXT{n:02d}", "nombres": "Caso", "nombre": f"ZZNEXT{n:02d}, Caso",
             "estado": "Activo", "sqlite_id": None})
    _clonar(conn, "designaciones", "institucion_id=1 AND departamento_id=1 AND periodo_id=9 AND estado='Activa' AND "
            "COALESCE(funcion_no_docente,0)=0", {"cuil": cuil, "dedicacion": dedicacion, "horas": horas,
                                                  "cargo": "Ayudante de Primera", "sqlite_id": None})
    return cuil


def _investigacion(conn, cuil: str, horas: float) -> None:
    _clonar(conn, "investigacion_docente", "institucion_id=1 AND departamento_id=1 AND periodo_id=9 AND "
            "estado_asignacion='Activa'", {"cuil": cuil, "horas_asignadas": horas, "sqlite_id": None})


def _sinteticos(conn) -> dict:
    casos = {}
    for n, horas in enumerate([3.95, 4, 4.99, 5, 6, 6.05, 10, 12], start=1):
        cuil = _docente(conn, n)
        _investigacion(conn, cuil, horas)
        casos[cuil] = horas * 10
    sin_act = _docente(conn, 20)
    cero = _docente(conn, 21, dedicacion="ZZNEXT", horas=0)
    _investigacion(conn, cero, 2)
    ext = _docente(conn, 22)
    _clonar(conn, "extension_docente", "institucion_id=1 AND departamento_id=1 AND periodo_id=9 AND "
            "estado_asignacion='Activa'", {"cuil": ext, "horas_asignadas": 3, "sqlite_id": None})
    # comision compartida (2 docentes) y comision individual (1 docente), 2 hs cada una (lunes 08-10)
    solo, a, b = _docente(conn, 30), _docente(conn, 31), _docente(conn, 32)
    ids = {}
    for etiqueta, cuiles in (("solo", [solo]), ("compartida", [a, b])):
        cid = _clonar(conn, "comisiones", "institucion_id=1 AND departamento_id=1 AND periodo_id=9 AND "
                      "COALESCE(estado,'Activa')='Activa'", {"nombre_comision": f"ZZNEXT {etiqueta}",
                                                              "sqlite_id": None})
        conn.execute("INSERT INTO horarios_comision (institucion_id, departamento_id, comision_id, dia, hora_inicio, "
                     "hora_fin, horas) VALUES (1, 1, %s, 'Domingo', '06:00', '08:00', 2)", [cid])
        for cuil in cuiles:
            _clonar(conn, "asignaciones_docentes_comision", "institucion_id=1 AND departamento_id=1",
                    {"comision_id": cid, "cuil": cuil, "estado": "Activa", "horas_asignadas": 2,
                     "usa_horario_personalizado": False, "sqlite_id": None})
        ids[etiqueta] = cid
    return {"pct": casos, "sin_actividad": sin_act, "cero": cero, "extension": ext, "solo": solo, "compartidos": [a, b]}


def test_productividad_sintetica_bordes_y_reglas(db_conn):
    with db_conn.transaction() as tx:
        s = _sinteticos(db_conn)
        c, n = certified_analisis(db_conn, INST, 1), motor(db_conn, INST, 1)
        pc, pn = c["get_docentes_productividad_periodo"](9), n["get_docentes_productividad_periodo"](9)
        assert igual_df(pc, pn)
        assert igual_df(c["construir_alertas_periodo"](9), n["construir_alertas_periodo"](9))
        por = {r["cuil"]: r for r in pn.to_dict("records")}
        esperado = {39.5: ("rojo", "Subutilización: baja carga registrada"), 40: ("amarillo", "Subutilización: baja carga registrada"),
                    49.9: ("amarillo", "Subutilización: baja carga registrada"), 50: ("amarillo", "Sin alerta principal"),
                    60: ("amarillo", "Sin alerta principal"), 60.5: ("verde", "Sin alerta principal"),
                    100: ("verde", "Sin alerta principal"),
                    120: ("azul", "Sobrecarga: horas utilizadas superan las contratadas")}
        for cuil, pct in s["pct"].items():
            r = por[cuil]
            assert r["porcentaje_uso"] == pytest.approx(round(pct, 2)) and r["horas_contratadas"] == 10
            color, diag = esperado[round(pct, 2)]
            assert P.color_productividad(r["porcentaje_uso"]) == color and r["diagnostico"] == diag
        assert por[s["sin_actividad"]]["diagnostico"] == "Sin actividad registrada"
        assert por[s["sin_actividad"]]["porcentaje_uso"] == 0
        assert por[s["cero"]]["horas_contratadas"] == 0 and por[s["cero"]]["porcentaje_uso"] == 0
        assert por[s["cero"]]["diagnostico"] == "Actividad registrada sin horas contratadas"
        assert por[s["extension"]]["horas_extension"] == 3 and por[s["extension"]]["porcentaje_uso"] == 30
        # Horas no lectivas (dep 1: 50 %): solo en la comision = 2 * 50 % = 1; compartida = 2 * 25 % = 0,5
        assert por[s["solo"]]["horas_comisiones_reales"] == 2 and por[s["solo"]]["horas_no_lectivas"] == 1
        for cuil in s["compartidos"]:
            assert por[cuil]["horas_comisiones_reales"] == 2 and por[cuil]["horas_no_lectivas"] == 0.5
        # Las horas del Dashboard derivan de la tabla de productividad (v162)
        m = n["get_metricas_analisis_periodo"](9)
        assert m["horas_no_lectivas"] == round(float(pn["horas_no_lectivas"].sum()), 2)
        assert m["horas_academicas_utilizadas"] == round(float(pn["horas_utilizadas"].sum()), 2)
        raise psycopg.Rollback(tx)


def test_semaforo_y_formato_del_codigo_no_de_la_leyenda():
    """D-AM13: el color sale del CODIGO (< 40 / <= 60 / <= 100 / > 100), no de la leyenda 0-39 / 40-60 / 61-100."""
    casos = {0: "rojo", 39.5: "rojo", 39.99: "rojo", 40: "amarillo", 49.9: "amarillo", 50: "amarillo", 60: "amarillo",
             60.5: "verde", 100: "verde", 100.01: "azul", 375: "azul"}
    for v, color in casos.items():
        assert P.color_productividad(v) == color, v
    assert P.color_productividad("x") == ""
    assert "61–100" in P.LEYENDA_SEMAFORO and "40–60" in P.LEYENDA_SEMAFORO
    assert P.fmt_max2(72.0) == "72" and P.fmt_max2(61.255, " %") == "61.26 %" and P.fmt_max2(float("nan")) == ""


def test_anomalias_certificadas_congeladas(db_conn):
    """D-AM13: se replican tal cual (deuda post-equivalencia)."""
    n = motor(db_conn, INST, 1)
    m = n["get_metricas_analisis_periodo"](9)
    alum = n["_alumnos_por_docente_periodo_v188"](9, metricas=m)
    # alumnos = 0 (inscriptos_asignatura_periodo vacia) y 66 vs 67 docentes en la misma tarjeta
    assert alum["alumnos_inscriptos"] == 0 and alum["alumnos_por_docente"] == 0
    assert m["docentes_en_comisiones"] == 66 and alum["docentes_en_comisiones_calculo"] == 67
    # prompt con el departamento fijo aunque el ambito sea otro
    n3 = motor(db_conn, INST, 3)
    prompt = n3["construir_prompt_ia_periodo"]("2026-2", n3["get_metricas_analisis_periodo"](10), pd.DataFrame(),
                                               pd.DataFrame())
    assert "Departamento de Informática e Ingeniería" in prompt
    # dep 3: % no lectivo mostrado 0 % con horas no lectivas > 0 (porcentaje de los departamentos de cada comision)
    m3 = n3["get_metricas_analisis_periodo"](10)
    assert m3["porcentaje_horas_no_lectivas"] == 0 and m3["horas_no_lectivas"] > 0
    # Comparacion: el "actual" es el ULTIMO periodo aunque se elija otro arriba
    per = P.periodos(n)
    op = P.comparacion_opciones(n, per["df"], {"id": 5, "nombre": "2026-1"})
    assert op["actual"] == {"id": 9, "nombre": "2026-2"}
    # LIMIT 1 sin ORDER BY en el periodo equivalente del ano anterior (SQL literal intacto en el motor)
    from pathlib import Path
    texto = (Path(P.__file__).resolve().parent / "motor" / "certificado.py").read_text(encoding="utf-8")
    bloque = texto[texto.index("def get_periodo_mismo_semestre_anio_anterior"):][:600]
    assert "LIMIT 1" in bloque and "ORDER BY" not in bloque


def test_lecturas_no_escriben_y_reconciliaciones_omitidas(db_conn):
    """D-AM2 / D-AM3: v208 / v212 / v214 no se ejecutan; el resultado de v205 / v206 lo reemplaza v208."""
    from analisis.motor import metadata
    n = motor(db_conn, INST, 1)
    for nombre in ("asegurar_movimientos_baja_efectiva_v208", "reconciliar_fechas_finalizacion_desde_movimientos_v212",
                   "reparar_bajas_historicas_confirmadas_v214"):
        assert metadata.TAREAS_SISTEMA[nombre] == "reconciliation" and n[nombre](9) is None
    antes = db_conn.execute("SELECT (SELECT md5(string_agg(md5(d::text),'' ORDER BY d.id)) FROM designaciones d), "
                            "(SELECT md5(string_agg(md5(m::text),'' ORDER BY m.id)) FROM movimientos m)").fetchone()
    m = n["get_metricas_analisis_periodo"](9)
    assert igual_df(m["df_mov"], n["get_movimientos"](9))  # v208 reemplaza el df_mov de v205/v206
    despues = db_conn.execute("SELECT (SELECT md5(string_agg(md5(d::text),'' ORDER BY d.id)) FROM designaciones d), "
                              "(SELECT md5(string_agg(md5(m::text),'' ORDER BY m.id)) FROM movimientos m)").fetchone()
    assert antes == despues
