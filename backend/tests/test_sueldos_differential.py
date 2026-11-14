"""Diferenciales de LECTURA de Sueldos sobre deptit_next_dev (ROLLBACK): el servicio NEXT vs la pagina certificada
transcrita (entry l. 61762-61931) y las funciones certificadas (``certified_sueldos``), desde el mismo estado.

- ⚙️ Escalas básicas: valores iniciales del formulario (mes -> aplicable anterior -> 06/2026) e historico.
- 📈 Tabla salarial: todas las dedicaciones y niveles.
- 👥 Sueldos del plantel: cada departamento y periodo real (actual / historico), mas filas ZZNEXT (cargo inexistente,
  dedicacion desconocida, antiguedad y posgrado informados, Ad Honorem, multiples designaciones, estados).
- Resumen docente: ``construir_tabla_sueldo_docente_v256`` con la cadena v162/v149 (incluido el Ad Honorem
  valorizado como rentado, H2) para docentes reales y sinteticos.
- Proyectos: costos v257/v258 de Investigacion y Extension (referencias 2026-2) y bordes sinteticos del motor.
- Escalas sinteticas (anteriores, futuras, multiples) y la institucion 5 sin escala.
"""

from __future__ import annotations

import pandas as pd
import pytest

from comisiones.service import records
from sueldos import rules as SR
from e5_b_support import filas_next, sueldo_resumen_independiente
from periodos_support import FIXED_TODAY
from sueldos_support import (  # noqa: F401  (fixtures)
    EXTRA_DEPARTMENTS, audit_store, certified_sueldos, db_conn, session_for, sueldos,
)

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")

INST = 1


def _rec(service, repo, inst=1, dep=1):
    if inst == 1 and dep == 1:
        return session_for(service, repo, 3)[0]
    sup = session_for(service, repo, 1)[0]
    service.set_context(sup, inst, dep, False)
    return sup


# ------------------------------------------------------------------------------------------ transcripciones
def cert_escalas(ns, mes_ref):
    escala_mes = ns["get_escala_salarial_mes_v256"](mes_ref)
    _, previa = ns["obtener_escala_aplicable_v256"](mes_ref)
    valores = {c: round(float(escala_mes.get(c, previa.get(c, ns["BASICOS_JUNIO_2026_V256"].get(c, 0.0))) or 0.0), 2)
               for c in ns["CARGOS"]}
    df = ns["get_escalas_salariales_v256"]()
    hist = []
    if not df.empty:
        h = df.copy()
        h["Mes"] = h["mes_referencia"].map(ns["_etiqueta_mes_v256"])
        h["Básico Simple"] = pd.to_numeric(h["basico_simple"], errors="coerce").fillna(0).map(ns["_moneda_v256"])
        for _, r in h.iterrows():
            hist.append({"Mes": r["Mes"], "Cargo": r["cargo"], "Básico Simple": r["Básico Simple"],
                         "Última actualización": pd.Timestamp(r["fecha_actualizacion"]).strftime("%Y-%m-%d %H:%M:%S"),
                         "Usuario": r["usuario_actualizacion"]})
    return valores, hist


def cert_plantel(ns, per_id):
    """Pestaña 3 (l. 61865-61929) con las funciones certificadas."""
    df_per_s = ns["get_periodos"]()
    fila_per_s = df_per_s[df_per_s["id"] == per_id]
    per_dict_s = fila_per_s.iloc[0].to_dict() if not fila_per_s.empty else {"id": per_id}
    mes_obj_s = ns["_mes_ref_desde_periodo_v256"](per_dict_s)
    mes_esc_s, escala_s = ns["obtener_escala_aplicable_v256"](mes_obj_s)
    if not escala_s:
        return {"estado": "sin_escala"}
    df_d_s = ns["get_designaciones"](per_id)
    df_doc_s = ns["get_docentes"]()
    if df_d_s.empty:
        return {"estado": "sin_designaciones", "mes": mes_esc_s}
    if not ns["es_periodo_historico_contexto_v182"](per_id) and "estado" in df_d_s.columns:
        df_d_s = df_d_s[df_d_s["estado"].fillna("Activa").astype(str).str.casefold().eq("activa")].copy()
    perfil = {}
    if isinstance(df_doc_s, pd.DataFrame) and not df_doc_s.empty:
        for _, rr in df_doc_s.iterrows():
            perfil[ns["_clave_cuil"](rr.get("cuil"))] = rr.to_dict()
    filas = []
    for _, rr in df_d_s.iterrows():
        pf = perfil.get(ns["_clave_cuil"](rr.get("cuil")), {})
        calc = ns["calcular_sueldo_designacion_v256"](rr.get("cargo"), rr.get("dedicacion"), rr.get("ad_honorem", "No"),
                                                      pf.get("antiguedad_anios"), pf.get("nivel_posgrado_salarial", ""),
                                                      escala_s)
        antig_inf = pf.get("antiguedad_anios") is not None
        try:
            antig_inf = antig_inf and not pd.isna(pf.get("antiguedad_anios"))
        except Exception:
            pass
        filas.append({
            "Docente": rr.get("nombre_completo", "") or pf.get("nombre_completo", ""),
            "CUIL": rr.get("cuil", ""), "Cargo": rr.get("cargo", ""), "Dedicación": rr.get("dedicacion", ""),
            "Antigüedad": f"{ns['_antiguedad_entera_v256'](pf.get('antiguedad_anios'))} años"
                          + ("" if antig_inf else " (no informada)"),
            "% antig.": f"{calc['porcentaje_antiguedad']*100:.0f}%",
            "Posgrado": ns["_nivel_posgrado_salarial_normalizado_v256"](pf.get("nivel_posgrado_salarial", "")) or "-",
            "% posgrado": f"{calc['porcentaje_posgrado']*100:.0f}%",
            "Ad Honorem": "Sí" if calc["ad_honorem"] else "No",
            "Básico dedicación": ns["_moneda_v256"](calc["basico_dedicacion"]),
            "Sueldo estimado": ns["_moneda_v256"](calc["total_estimado"]),
            "_total": calc["total_estimado"],
        })
    if not filas:
        return {"estado": "vacio", "mes": mes_esc_s}
    df = pd.DataFrame(filas)
    return {"estado": "ok", "mes": mes_esc_s, "docentes": int(df["CUIL"].astype(str).map(ns["_clave_cuil"]).nunique()),
            "designaciones": len(df), "total": ns["_moneda_v256"](float(pd.to_numeric(df["_total"]).fillna(0).sum())),
            "filas": [{k: v for k, v in f.items() if k != "_total"} for f in filas]}


def _clave_fila(f):
    return tuple(str(f[k]) for k in ("CUIL", "Cargo", "Dedicación", "Ad Honorem", "Sueldo estimado", "Docente"))


def comparar_plantel(sueldos, rec, ns, per_id):
    a = sueldos.plantel(rec, {"periodo_id": per_id})
    b = cert_plantel(ns, per_id)
    assert a["estado"] == b["estado"], (per_id, a, b)
    if b["estado"] == "ok":
        assert a["caption_escala"] == f"Escala aplicada automáticamente: **{SR.etiqueta_mes_v256(b['mes'])}**."
        assert (a["metricas"]["docentes"], a["metricas"]["designaciones"], a["metricas"]["total"]) == \
            (b["docentes"], b["designaciones"], b["total"])
        # Orden: el certificado empata por apellido/nombres sin desempate; NEXT agrega d.id (lectura de Designaciones).
        assert sorted(map(_clave_fila, a["filas"])) == sorted(map(_clave_fila, b["filas"]))
        assert sorted(a["filas"], key=_clave_fila) == sorted(b["filas"], key=_clave_fila)
    return a, b


# ------------------------------------------------------------------------------------------ escalas
@pytest.mark.parametrize("mes", ["2026-06", "2026-10", "2026-05", "2027-01", "2000-01", "2100-12"])
def test_escalas_basicas_formulario_e_historico(service, repo, db_conn, sueldos, mes):
    rec = _rec(service, repo)
    ns = certified_sueldos(db_conn, INST, 1)
    anio, m = (int(x) for x in mes.split("-"))
    r = sueldos.escalas(rec, {"anio": anio, "mes": m})
    valores, hist = cert_escalas(ns, mes)
    assert r["valores"] == valores and r["historico"] == hist
    assert r["mes_referencia"] == mes and r["etiqueta"] == SR.etiqueta_mes_v256(mes)


def _insertar_escala(db_conn, inst, mes, factor, usuario="ZZNEXT test"):
    for cargo, basico in SR.BASICOS_JUNIO_2026_V256.items():
        db_conn.execute("INSERT INTO escalas_salariales_docentes (institucion_id, mes_referencia, cargo, basico_simple, "
                        "usuario_actualizacion) VALUES (%s,%s,%s,%s,%s)", [inst, mes, cargo, round(basico * factor, 2),
                                                                           usuario])


def test_escalas_sinteticas_anterior_futura_y_multiples(service, repo, db_conn, sueldos):
    _insertar_escala(db_conn, INST, "2025-12", 0.9)
    _insertar_escala(db_conn, INST, "2026-09", 1.1)
    _insertar_escala(db_conn, INST, "2027-03", 1.3)
    db_conn.execute("INSERT INTO escalas_salariales_docentes (institucion_id, mes_referencia, cargo, basico_simple) "
                    "VALUES (1, '2026-08', 'ZZNEXT Cargo', 1)")
    rec = _rec(service, repo)
    ns = certified_sueldos(db_conn, INST, 1)
    for mes in ["2025-11", "2025-12", "2026-01", "2026-07", "2026-08", "2026-09", "2026-10", "2027-03", "2027-12"]:
        anio, m = (int(x) for x in mes.split("-"))
        r = sueldos.escalas(rec, {"anio": anio, "mes": m})
        assert (r["valores"], r["historico"]) == cert_escalas(ns, mes), mes
    # Tabla salarial: todos los meses disponibles, dedicaciones y niveles
    meses = sueldos.tabla(rec, {})["meses"]
    assert [x["valor"] for x in meses] == ["2027-03", "2026-09", "2026-08", "2026-06", "2025-12"]
    for mes in [x["valor"] for x in meses]:
        for ded in SR.DEDICACIONES_TABLA:
            for nivel in SR.NIVELES_POSGRADO_SALARIAL_V256:
                t = sueldos.tabla(rec, {"mes_referencia": mes, "dedicacion": ded, "nivel": nivel})
                assert t["filas"] == SR.tabla_salarial_v256(ns["get_escala_salarial_mes_v256"](mes), ded, nivel)
    # Plantel: periodo actual -> mes de HOY (2026-10) -> 2026-09; historico 2026-1 (fin 2026-07-31) -> 2026-06.
    a, _ = comparar_plantel(sueldos, rec, ns, 9)
    assert "09/2026" in a["caption_escala"]
    a, _ = comparar_plantel(sueldos, rec, ns, 5)
    assert "06/2026" in a["caption_escala"]


def test_historicos_se_recalculan_al_vuelo_sin_snapshot(service, repo, db_conn, sueldos):
    """Editar la escala 06/2026 cambia en el acto el sueldo calculado del periodo CERRADO 2026-1 (replicado)."""
    rec = _rec(service, repo)
    antes = sueldos.plantel(rec, {"periodo_id": 5})["metricas"]["total"]
    db_conn.execute("UPDATE escalas_salariales_docentes SET basico_simple = basico_simple * 2 "
                    "WHERE institucion_id=1 AND mes_referencia='2026-06'")
    despues = sueldos.plantel(rec, {"periodo_id": 5})
    assert despues["metricas"]["total"] != antes
    comparar_plantel(sueldos, rec, certified_sueldos(db_conn, INST, 1), 5)


def test_institucion_sin_escala(service, repo, db_conn, sueldos):
    """Institucion 5 (sin departamentos ni escala): formulario con los basicos 06/2026, historico vacio, tabla sin
    meses, plantel con aviso institucional.  No se siembra nada (H4)."""
    rec = _rec(service, repo, inst=5, dep=None)
    antes = db_conn.execute("SELECT count(*) FROM escalas_salariales_docentes").fetchone()[0]
    ov = sueldos.overview(rec)
    assert ov["contexto"]["departamento"] is None and ov["plantel"] == {"disponible": False,
                                                                        "mensaje": ov["plantel"]["mensaje"]}
    ns = certified_sueldos(db_conn, 5, None)
    r = sueldos.escalas(rec, {"anio": 2026, "mes": 10})
    assert r["valores"] == SR.BASICOS_JUNIO_2026_V256 == cert_escalas(ns, "2026-10")[0]
    assert r["historico"] == [] and r["mensaje_historico"] == "Todavía no hay escalas salariales cargadas."
    assert sueldos.tabla(rec, {}) == {"meses": [], "mensaje": "Cargá primero una escala salarial."}
    assert ns["obtener_escala_aplicable_v256"]("2026-10") == (None, {})
    assert db_conn.execute("SELECT count(*) FROM escalas_salariales_docentes").fetchone()[0] == antes


# ------------------------------------------------------------------------------------------ plantel
def _plantel_independiente(conn, dep, pid) -> dict:
    """Metricas del plantel del periodo actual con SQL propio + reglas certificadas puras (solo Activas)."""
    import pandas as pd
    from sueldos import rules as SR
    filas = conn.execute(
        "SELECT d.cuil, d.cargo, d.dedicacion, COALESCE(d.ad_honorem, 'No'), doc.antiguedad_anios, "
        "COALESCE(doc.nivel_posgrado_salarial, '') FROM designaciones d LEFT JOIN docentes doc ON "
        "regexp_replace(doc.cuil, '[^0-9]', '', 'g') = regexp_replace(d.cuil, '[^0-9]', '', 'g') AND "
        "doc.institucion_id = d.institucion_id AND doc.departamento_id = d.departamento_id WHERE d.institucion_id = 1 "
        "AND d.departamento_id = %s AND d.periodo_id = %s AND COALESCE(d.estado, 'Activa') = 'Activa'",
        [dep, pid]).fetchall()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM escalas_salariales_docentes WHERE institucion_id = 1")
        escalas = pd.DataFrame(cur.fetchall(), columns=[x.name for x in cur.description])
    _, escala = SR.escala_aplicable_v256(escalas, None, FIXED_TODAY)
    total = sum(SR.calcular_sueldo_designacion_v256(c, d, a, ant, niv, escala)["total_estimado"]
                for _, c, d, a, ant, niv in filas)
    return {"docentes": len({SR.clave_cuil(f[0]) for f in filas}), "designaciones": len(filas),
            "total": SR.moneda_v256(total)}


@pytest.mark.parametrize("dep,periodo", [(1, "2026-2"), (1, "2026-1"), (2, "2026-2"), (2, "2026-1"), (3, "2026-2"),
                                         (3, "2026-1"), (4, "2026-2"), (4, "2026-1"), (9, "2026-2"), (9, "2026-1"),
                                         (11, "2026-1")])
def test_plantel_real_por_departamento_y_periodo(service, repo, db_conn, sueldos, dep, periodo):
    rec = _rec(service, repo, dep=dep)
    pid = db_conn.execute("SELECT id FROM periodos WHERE institucion_id=1 AND departamento_id=%s AND nombre=%s",
                          [dep, periodo]).fetchone()[0]
    ns = certified_sueldos(db_conn, INST, dep)
    a, b = comparar_plantel(sueldos, rec, ns, pid)
    if (dep, periodo) == (1, "2026-2"):  # Etapa 5 / C2: esperado por SQL + reglas (antes literales de la base dev)
        assert a["metricas"] == _plantel_independiente(db_conn, dep, pid)
    if (dep, periodo) == (3, "2026-2"):
        adh = [f for f in a["filas"] if f["Ad Honorem"] == "Sí"]
        n_adh = db_conn.execute("SELECT count(*) FROM designaciones WHERE institucion_id = 1 AND departamento_id = 3 "
                                "AND periodo_id = %s AND estado = 'Activa' AND ad_honorem = 'Sí'", [pid]).fetchone()[0]
        assert len(adh) == n_adh > 0 and {f["Sueldo estimado"] for f in adh} == {"$ 0,00"}
    if periodo == "2026-1" and a["estado"] == "ok":  # historico: todas las designaciones (Finalizadas)
        assert a["metricas"]["designaciones"] == b["designaciones"]


ZZ_CUIL_A, ZZ_CUIL_B, ZZ_CUIL_C = "27999000001", "27999000002", "27999000003"


def _sinteticos(db_conn, dep=1, periodo=9, cerrado_periodo=5):
    """Docentes ZZNEXT con antiguedad/posgrado informados y designaciones con bordes del motor."""
    for cuil, antig, nivel in [(ZZ_CUIL_A, 12, "Doctora"), (ZZ_CUIL_B, 23, "maestria"), (ZZ_CUIL_C, None, "PhD")]:
        db_conn.execute("INSERT INTO docentes (institucion_id, departamento_id, cuil, apellido, nombres, estado, "
                        "tipo_docente, antiguedad_anios, nivel_posgrado_salarial) VALUES (1,%s,%s,'ZZNEXT',%s,'Activo',"
                        "'Propio',%s,%s)", [dep, cuil, cuil[-1], antig, nivel])
    filas = [
        (ZZ_CUIL_A, "Titular", "Exclusiva", 40, "No", "Activa"),
        (ZZ_CUIL_A, "Adjunto", "Simple", 10, "Sí", "Activa"),
        (ZZ_CUIL_A, "JTP", "Semiexclusiva", 20, "No", "Suspendida"),
        (ZZ_CUIL_B, "Profesor Adjunto", "Parcial", 20, "No", "Activa"),
        (ZZ_CUIL_B, "Asociado", "ZZNEXT dedicación", 0, None, "Activa"),
        (ZZ_CUIL_C, "Ayudante 1ra", "Simple Ad Honorem", 10, "No", "Activa"),
        (ZZ_CUIL_C, "JTP 2026-2", "Simple", 10, "No", "Activa"),
        (ZZ_CUIL_C, "Ayudante 2da", "parcial", 20, "SI", "Baja"),
    ]
    for cuil, cargo, ded, hs, adh, estado in filas:
        db_conn.execute("INSERT INTO designaciones (institucion_id, departamento_id, periodo_id, cuil, cargo, dedicacion, "
                        "horas, ad_honorem, estado, tipo_designacion, observaciones, fecha_desde, fecha_hasta) VALUES "
                        "(1,%s,%s,%s,%s,%s,%s,%s,%s,'Interino','ZZNEXT','2026-08-01','2026-12-31')",
                        [dep, periodo, cuil, cargo, ded, hs, adh, estado])
    db_conn.execute("INSERT INTO designaciones (institucion_id, departamento_id, periodo_id, cuil, cargo, dedicacion, "
                    "horas, ad_honorem, estado, tipo_designacion, observaciones) VALUES "
                    "(1,%s,%s,%s,'Titular','Simple',10,'No','Activa','Interino','ZZNEXT')", [dep, cerrado_periodo,
                                                                                             ZZ_CUIL_A])


def test_plantel_sintetico_bordes(service, repo, db_conn, sueldos):
    _sinteticos(db_conn)
    rec = _rec(service, repo)
    ns = certified_sueldos(db_conn, INST, 1)
    a, _ = comparar_plantel(sueldos, rec, ns, 9)
    zz = {(f["CUIL"], f["Cargo"]): f for f in a["filas"] if f["CUIL"].startswith("27999")}
    assert zz[(ZZ_CUIL_A, "Titular")]["Antigüedad"] == "12 años" and zz[(ZZ_CUIL_A, "Titular")]["Posgrado"] == "Doctor"
    assert zz[(ZZ_CUIL_A, "Titular")]["% antig."] == "60%" and zz[(ZZ_CUIL_A, "Titular")]["% posgrado"] == "18%"
    assert zz[(ZZ_CUIL_A, "Adjunto")]["Sueldo estimado"] == "$ 0,00"          # Ad Honorem en el plantel: $0
    assert (ZZ_CUIL_A, "JTP") not in zz                                         # Suspendida: solo Activas (actual)
    assert zz[(ZZ_CUIL_B, "Profesor Adjunto")]["Sueldo estimado"] == "$ 0,00"  # cargo sin match exacto
    assert zz[(ZZ_CUIL_B, "Asociado")]["Básico dedicación"] == "$ 433.482,17"   # dedicacion desconocida x1
    assert zz[(ZZ_CUIL_C, "Ayudante 1ra")]["Ad Honorem"] == "No"               # legacy "Simple Ad Honorem" + 'No'
    assert zz[(ZZ_CUIL_C, "Ayudante 1ra")]["Antigüedad"] == "0 años (no informada)"
    assert zz[(ZZ_CUIL_C, "Ayudante 1ra")]["Posgrado"] == "-"
    assert (ZZ_CUIL_C, "Ayudante 2da") not in zz
    comparar_plantel(sueldos, rec, ns, 5)


def test_plantel_validaciones_y_ambito_departamental(service, repo, db_conn, sueldos):
    from sueldos.service import SueldosError
    rec = _rec(service, repo)
    otro = db_conn.execute("SELECT id FROM periodos WHERE departamento_id=2 AND nombre='2026-2'").fetchone()[0]
    for malo in (otro, "9", None, True, 999999):
        with pytest.raises(SueldosError) as e:
            sueldos.plantel(rec, {"periodo_id": malo})
        assert e.value.status in (409, 422)
    ov = sueldos.overview(rec)
    assert ov["plantel"]["periodo_defecto"] == "2026-2"
    assert [p["nombre"] for p in ov["plantel"]["periodos"]] == ["2026-2", "2026-1"]


# ------------------------------------------------------------------------------------------ Resumen docente
def _cert_resumen(ns, cuil, per_id):
    df_doc = ns["get_resumen_docente"](cuil)[0]
    fila_doc = df_doc.iloc[0]
    nivel = ns["_nivel_posgrado_salarial_normalizado_v256"](fila_doc.get("nivel_posgrado_salarial", ""))
    antig = fila_doc.get("antiguedad_anios")
    df_per = ns["get_periodos"]()
    fila = df_per[df_per["id"] == per_id]
    per = fila.iloc[0].to_dict() if not fila.empty else {"id": per_id}
    mes_obj = ns["_mes_ref_desde_periodo_v256"](per)
    return per, antig, nivel, mes_obj, ns["construir_tabla_sueldo_docente_v256"](cuil, per_id, antig, nivel, mes_obj)


def _comparar_resumen(sueldos, rec, ns, cuil, per_id):
    """1) La REPLICA certificada NEXT (``construir_tabla_sueldo_docente`` con la fuente v162) es identica al certificado.
    2) El Resumen NEXT CORREGIDO (Etapa 5 / Tanda B, B1: Ad Honorem $0, solo Activas en el periodo no cerrado,
    antiguedad/posgrado de la ficha) es igual al calculo INDEPENDIENTE (``e5_b_support``).  Devuelve
    ``(replica, corregido)``."""
    per, antig, nivel, mes_obj, (mes_c, df_c, tot_c) = _cert_resumen(ns, cuil, per_id)
    assert antig is None and nivel == ""  # get_resumen_docente no selecciona el perfil salarial (deuda H2)
    scope = sueldos.scope(rec)
    mes_n, df_n, tot_n = sueldos._read(scope, lambda m: m.construir_tabla_sueldo_docente(cuil, per_id, None, "", mes_obj))
    assert mes_n == mes_c and records(df_n) == records(df_c) and tot_n == tot_c
    replica = {"filas": records(df_c), "total": tot_c}
    r = sueldos.sueldo_docente_resumen(scope, cuil, per)
    assert r["mes_objetivo"] == mes_obj
    conn = sueldos._read(scope, lambda m: m.repo._conn)
    esperado = sueldo_resumen_independiente(conn, scope.institution_id, scope.department_id, cuil, per_id, mes_obj,
                                            FIXED_TODAY)
    if not esperado["filas"] or not esperado["mes_escala"]:
        assert r["estado"] in ("sin_escala", "sin_designaciones")
        return replica, r
    assert r["estado"] == "ok" and r["mes_escala"] == esperado["mes_escala"]
    assert filas_next(r) == esperado["filas"] and r["total"] == esperado["total"]
    assert r["total_formateado"] == ns["_moneda_v256"](esperado["total"])
    return replica, r


def test_resumen_cadena_institucional_docentes_reales(service, repo, db_conn, sueldos):
    casos = db_conn.execute("""
        SELECT DISTINCT ON (d.departamento_id, d.periodo_id, (COALESCE(d.ad_honorem,'No')='Sí'), d.estado,
                            d.dedicacion) d.departamento_id, d.periodo_id, d.cuil
        FROM designaciones d JOIN docentes doc ON doc.cuil=d.cuil AND doc.departamento_id=d.departamento_id
        WHERE d.institucion_id=1 ORDER BY d.departamento_id, d.periodo_id, (COALESCE(d.ad_honorem,'No')='Sí'),
                 d.estado, d.dedicacion, d.cuil""").fetchall()
    multi = db_conn.execute("""SELECT min(d.departamento_id), min(d.periodo_id), d.cuil FROM designaciones d
        JOIN periodos p ON p.id=d.periodo_id WHERE d.institucion_id=1 AND p.nombre='2026-2' GROUP BY d.cuil
        HAVING count(DISTINCT d.departamento_id) > 1 ORDER BY d.cuil LIMIT 5""").fetchall()
    vistos = 0
    for dep, pid, cuil in list(casos) + list(multi):
        rec = _rec(service, repo, dep=dep)
        _comparar_resumen(sueldos, rec, certified_sueldos(db_conn, INST, dep), cuil, pid)
        vistos += 1
    assert vistos >= 25


def test_resumen_ad_honorem_valorizado_como_rentado_h2(service, repo, db_conn, sueldos):
    """H2 (certificado): una designacion Ad Honorem 'Sí' vale $0 en el plantel pero el Resumen certificado la valoriza
    como rentada (la fuente v149 no trae ``ad_honorem``).  Etapa 5 / Tanda B (B1): el Resumen NEXT la CORRIGE ($0)."""
    rec = _rec(service, repo)
    cuil = db_conn.execute("""SELECT d.cuil FROM designaciones d WHERE d.institucion_id=1 AND d.departamento_id=1
        AND d.periodo_id=9 AND d.ad_honorem='Sí' AND d.estado='Activa' AND d.cargo='Titular' AND d.dedicacion='Simple'
        ORDER BY d.cuil LIMIT 1""").fetchone()[0]
    ns = certified_sueldos(db_conn, INST, 1)
    replica, r = _comparar_resumen(sueldos, rec, ns, cuil, 9)
    cert = [f for f in replica["filas"] if f["Cargo"] == "Titular" and f["Dedicación"] == "Simple"]
    assert cert and cert[0]["Ad Honorem"] == "No" and cert[0]["Sueldo estimado"] == 584573.72  # anomalia certificada
    titular = [f for f in r["filas"] if f["Cargo"] == "Titular" and f["Dedicación"] == "Simple"]
    assert titular and titular[0]["Ad Honorem"] == "Sí" and titular[0]["Sueldo estimado"] == 0.0  # NEXT corregido
    plantel = sueldos.plantel(rec, {"periodo_id": 9})["filas"]
    en_plantel = [f for f in plantel if f["CUIL"] == cuil and f["Cargo"] == "Titular"]
    assert en_plantel and en_plantel[0]["Ad Honorem"] == "Sí" and en_plantel[0]["Sueldo estimado"] == "$ 0,00"


def test_resumen_sintetico_suspendidas_bajas_y_perfil(service, repo, db_conn, sueldos):
    _sinteticos(db_conn)
    rec = _rec(service, repo)
    ns = certified_sueldos(db_conn, INST, 1)
    replica, a = _comparar_resumen(sueldos, rec, ns, ZZ_CUIL_A, 9)
    assert {f["Cargo"] for f in replica["filas"]} == {"Titular", "Adjunto", "JTP"}  # certificado: incluye la Suspendida
    # La ficha tiene 12 anios y "Doctora", pero el Resumen certificado no los lee: 0 anios (20%), sin posgrado.
    assert {(f["Antigüedad"], f["Posgrado"]) for f in replica["filas"]} == {("0 años (20%)", "Sin adicional (0%)")}
    # Etapa 5 / B1: NEXT solo Activas (sin la Suspendida), Ad Honorem $0 y el perfil de la ficha (12 anios, Doctor).
    assert {f["Cargo"] for f in a["filas"]} == {"Titular", "Adjunto"}  # sin la JTP Suspendida
    assert all(f["Antigüedad"].startswith("12 años") and f["Posgrado"].startswith("Doctor") for f in a["filas"])
    assert [f["Sueldo estimado"] for f in a["filas"] if f["Cargo"] == "Adjunto"] == [0.0]  # Ad Honorem
    assert sueldos.plantel(rec, {"periodo_id": 9})["filas"] and any(
        f["Posgrado"] == "Doctor" for f in sueldos.plantel(rec, {"periodo_id": 9})["filas"])  # el plantel si
    replica_c, c = _comparar_resumen(sueldos, rec, ns, ZZ_CUIL_C, 9)
    assert "JTP 2026-2" not in {f["Cargo"] for f in replica_c["filas"]}       # v265 descarta el cargo concatenado
    assert "Ayudante 2da" in {f["Cargo"] for f in replica_c["filas"]}         # certificado: Baja incluida por v149
    assert "Ayudante 2da" not in {f["Cargo"] for f in c["filas"]}             # NEXT (B1): la Baja no se valoriza
    _comparar_resumen(sueldos, rec, ns, ZZ_CUIL_B, 9)
    _comparar_resumen(sueldos, rec, ns, ZZ_CUIL_A, 5)                          # historico (Cerrado)
    # sin designaciones en el periodo: tabla vacia en ambos ("No hay designaciones para calcular sueldo...")
    assert ns["construir_tabla_sueldo_docente_v256"]("20000000000", 9, None, "", "2026-10")[1].empty
    r = sueldos.sueldo_docente_resumen(sueldos.scope(rec), "20000000000", {"id": 9})
    assert r["estado"] == "sin_designaciones" and r["mensaje"] == "No hay designaciones para calcular sueldo en este período."


# ------------------------------------------------------------------------------------------ proyectos (v257/v258)
def _cert_costos(ns, tipo):
    periodo_actual = ns["get_periodo_abierto"]()
    obtener = ns["get_investigacion_docente" if tipo == "investigacion" else "get_extension_docente"]
    df = obtener(incluir_bajas=True, todos_departamentos=True)
    nombre = str(periodo_actual.get("nombre") or "").strip()
    act = df[df["periodo"].fillna("").astype(str).str.strip().eq(nombre)].copy()
    if ns["es_periodo_historico_contexto_v182"](periodo_actual.get("id")):
        act = ns["_filtrar_asignaciones_proyecto_cierre_v183"](act, periodo_actual.get("id"))
    elif "estado_asignacion" in act.columns:
        act = act[act["estado_asignacion"].fillna("Activa").astype(str).str.strip().str.casefold().eq("activa")].copy()
    return periodo_actual, act, ns["calcular_costos_asignaciones_proyecto_v257"](act, periodo_actual)


COLS_COSTO = ["cargo_salarial_v257", "dedicacion_salarial_v257", "condicion_salarial_v257",
              "horas_contractuales_rentadas_v257", "sueldo_mensual_docente_v257", "tarifa_mensual_por_hora_v257",
              "costo_mensual_proyecto_v257", "meses_ejecucion_v258", "costo_total_proyecto_v258"]


def _por_id(df):
    return {int(r["id"]): tuple(r[c] for c in COLS_COSTO) for _, r in df.iterrows()}


@pytest.mark.parametrize("tipo,dep", [("investigacion", 1), ("investigacion", 3), ("extension", 1), ("extension", 9)])
def test_costos_proyectos_vigentes_referencias_2026_2(service, repo, db_conn, sueldos, tipo, dep):
    """Etapa 5 / C2: sin totales ni conteos absolutos de la base dev (antes 1301759612.16 / 139 / 49 y 87148362.24 /
    17 / 12): NEXT = certificado en total, detalle por id y proyectos; el total es institucional (igual en todos los
    departamentos de la institucion)."""
    rec = _rec(service, repo, dep=dep)
    ns = certified_sueldos(db_conn, INST, dep)
    _, _, (mes_c, det_c, tot_c) = _cert_costos(ns, tipo)
    r = sueldos.costos_proyectos_vigentes(sueldos.scope(rec), tipo)
    assert r["mes_escala"] == mes_c and r["total"] == tot_c > 0
    assert len(r["detalle"]) == len(det_c) > 0 and len(r["por_proyecto"]) == int(det_c["proyecto_id"].nunique())
    otro = sueldos.costos_proyectos_vigentes(sueldos.scope(_rec(service, repo, dep=1)), tipo)
    assert otro["total"] == r["total"]
    assert _por_id(r["detalle"]) == _por_id(det_c)
    condiciones = set(r["detalle"]["condicion_salarial_v257"])
    if tipo == "investigacion":
        assert {"Rentada", "Mixta (rentada + Ad Honorem)"} <= condiciones
        assert (r["detalle"]["cargo_salarial_v257"].str.contains(r"\+")).any()          # varios cargos
        assert ((pd.to_numeric(r["detalle"]["horas_asignadas"]) == 0)
                & (r["detalle"]["costo_total_proyecto_v258"] == 0)).any()              # 0 horas -> $0
        assert r["detalle"]["departamento_asignacion_id"].nunique() > 1                  # varios departamentos


def test_motor_v257_bordes_sinteticos(service, repo, db_conn, sueldos):
    """Mismo DataFrame de entrada (contrato del helper) al motor certificado y al de NEXT."""
    _sinteticos(db_conn)
    rec = _rec(service, repo)
    ns = certified_sueldos(db_conn, INST, 1)
    pa = ns["get_periodo_abierto"]()
    real = db_conn.execute("SELECT cuil FROM designaciones WHERE institucion_id=1 AND departamento_id=3 AND "
                           "periodo_id=10 AND estado='Activa' AND ad_honorem='No' ORDER BY cuil LIMIT 1").fetchone()[0]
    filas = [
        (1, 101, ZZ_CUIL_A, 10, 1, "2026-01-01", "2027-12-31"),      # mixta + suspendida excluida
        (2, 101, ZZ_CUIL_B, 5.5, 1, "2026-03-01", "2026-03-10"),     # cargo sin match + dedicacion desconocida; 1 mes
        (3, 102, ZZ_CUIL_C, 8, None, "2026-01-01", "2026-12-31"),    # departamento nulo -> el de la sesion
        (4, 102, "20111111119", 10, 1, "2026-01-01", "2026-12-31"),  # sin designacion
        (5, 103, real, 10, 1, "2026-01-01", "2026-12-31"),           # prestado: solo designacion en otro depto
        (6, 103, ZZ_CUIL_A, -4, 1, "2026-01-01", "2026-12-31"),      # horas negativas -> 0
        (7, 104, ZZ_CUIL_A, None, 1, None, "2026-12-31"),            # sin fechas -> 0 meses
        (8, 104, ZZ_CUIL_A, 10, 1, "2027-01-01", "2026-01-01"),      # fin < inicio
    ]
    df = pd.DataFrame(filas, columns=["id", "proyecto_id", "cuil", "horas_asignadas", "departamento_asignacion_id",
                                      "fecha_inicio", "fecha_fin"])
    m_c, det_c, tot_c = ns["calcular_costos_asignaciones_proyecto_v257"](df.copy(), pa)
    r = sueldos.costos_asignaciones(sueldos.scope(rec), df.copy(), pa)
    assert (r["mes_escala"], r["total"]) == (m_c, tot_c) and _por_id(r["detalle"]) == _por_id(det_c)
    cond = dict(zip(r["detalle"]["id"], r["detalle"]["condicion_salarial_v257"]))
    assert cond[1] == "Mixta (rentada + Ad Honorem)" and cond[4] == "Sin designación" and cond[5] == "Rentada"
    # sin periodo de contexto -> sin costos; DataFrame vacio -> (None, vacio, 0)
    assert sueldos.costos_asignaciones(sueldos.scope(rec), df.copy(), None)["total"] == 0.0
    assert ns["calcular_costos_asignaciones_proyecto_v257"](df.copy(), None)[2] == 0.0
    vacio = sueldos.costos_asignaciones(sueldos.scope(rec), pd.DataFrame(), pa)
    assert vacio["mes_escala"] is None and vacio["total"] == 0.0
