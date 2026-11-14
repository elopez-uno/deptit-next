"""Etapa 5 / Tanda B — correctness funcional con datos reales (READ ONLY / ROLLBACK).

- B1 Sueldo estimado del Resumen docente: Ad Honorem $0, solo Activas en el periodo no cerrado, antiguedad y posgrado
  de la ficha; verificado contra un calculo INDEPENDIENTE para TODOS los docentes con designaciones en los periodos
  abiertos, y coherente con el plantel de Sueldos para los docentes de un solo departamento.
- B2 E4-04 frente a E4-05: el sueldo mensual que v257 usa para la tarifa de cada asignacion de Investigacion /
  Extension es igual al total del Resumen salvo los docentes con designaciones en varios departamentos (por diseno).
- B4 Normalizador de encabezados: reconoce "Años antigüedad" / "N° resolución" y variantes; para todo encabezado que
  el certificado ya reconocia el resultado es identico.
- B5 Round-trip de los modelos Excel: cada encabezado de cada modelo oficial lo reconoce su propio lector.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from io import BytesIO

import pandas as pd
import pytest
from openpyxl import load_workbook

from e5_b_support import filas_next, sueldo_resumen_independiente
from periodos_support import FIXED_TODAY, audit_store, db_conn  # noqa: F401
from saas_support import auth_db  # noqa: F401

HOY = date(2026, 11, 2)
pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")  # pandas read_sql con DBAPI (motor certificado)


def _motor(conn, inst, dep):
    from sueldos.lecturas import Motor
    from sueldos.repository import SueldosRepository
    return Motor(SueldosRepository(conn, inst, dep), HOY)


def _resumen(m, cuil, pid) -> dict:
    from sueldos.lecturas import ficha_salarial
    f = ficha_salarial(m, cuil)
    mes = m.mes_ref_desde_periodo({"id": pid})
    mes_esc, df, total = m.construir_tabla_sueldo_docente(cuil, pid, f["antiguedad_anios"], f["nivel_posgrado_salarial"],
                                                          mes, fuente=m.designaciones_sueldo_resumen(cuil, pid))
    filas = [{"Cargo": r["Cargo"], "Dedicación": r["Dedicación"], "Ad Honorem": r["Ad Honorem"],
              "Sueldo estimado": r["Sueldo estimado"]} for _, r in df.iterrows()]
    return {"mes": mes, "mes_escala": mes_esc, "filas": filas, "total": total}


def _abiertos(conn):
    return conn.execute("SELECT institucion_id, departamento_id, id FROM periodos WHERE estado = 'Abierto' "
                        "ORDER BY 1, 2").fetchall()


# ------------------------------------------------------------------------------------------ B1
def test_b1_resumen_igual_al_calculo_independiente_en_todos_los_docentes(db_conn):
    verificados, con_adh = 0, 0
    for inst, dep, pid in _abiertos(db_conn):
        m = _motor(db_conn, inst, dep)
        cuiles = [r[0] for r in db_conn.execute(
            "SELECT DISTINCT d.cuil FROM designaciones d JOIN docentes x ON x.cuil = d.cuil AND x.institucion_id = "
            "d.institucion_id AND x.departamento_id = d.departamento_id WHERE d.institucion_id = %s AND "
            "d.departamento_id = %s AND d.periodo_id = %s", [inst, dep, pid])]
        for cuil in cuiles:
            r = _resumen(m, cuil, pid)
            esperado = sueldo_resumen_independiente(db_conn, inst, dep, cuil, pid, r["mes"], HOY)
            assert filas_next(r) == esperado["filas"] and r["total"] == esperado["total"]
            assert all(f["Sueldo estimado"] == 0 for f in r["filas"] if f["Ad Honorem"] == "Sí")
            verificados += 1
            con_adh += esperado["ad_honorem_en_db"] > 0
    assert verificados >= 600 and con_adh >= 100


def test_b1_coherente_con_el_plantel_de_sueldos(db_conn):
    """Docentes con designaciones Activas solo en el departamento de la sesion: total del Resumen = suma del plantel."""
    from sueldos import rules as SR
    comparados = 0
    for inst, dep, pid in _abiertos(db_conn):
        m = _motor(db_conn, inst, dep)
        plantel = m.plantel({"id": pid})
        if plantel.get("estado") != "ok":
            continue
        por_cuil: dict = {}
        for f in plantel["filas"]:
            v = f["Sueldo estimado"]
            if isinstance(v, str):
                v = float(v.replace("$", "").replace(".", "").replace(",", ".").strip())
            por_cuil[SR.clave_cuil(f["CUIL"])] = por_cuil.get(SR.clave_cuil(f["CUIL"]), 0.0) + float(v)
        nombre = db_conn.execute("SELECT nombre FROM periodos WHERE id = %s", [pid]).fetchone()[0]
        unicos = [r[0] for r in db_conn.execute(
            "SELECT regexp_replace(d.cuil, '[^0-9]', '', 'g') FROM designaciones d JOIN periodos p ON p.id = d.periodo_id "
            "WHERE d.institucion_id = %s AND p.nombre = %s AND COALESCE(d.estado, 'Activa') = 'Activa' "
            "GROUP BY 1 HAVING count(DISTINCT d.departamento_id) = 1 AND min(d.departamento_id) = %s",
            [inst, nombre, dep])]
        for clave in unicos:
            if clave in por_cuil:
                assert round(_resumen(m, clave, pid)["total"], 2) == round(por_cuil[clave], 2), (dep, "docente")
                comparados += 1
    assert comparados >= 500


# ------------------------------------------------------------------------------------------ B2
def test_b2_costos_v257_reconciliados_con_el_resumen(db_conn):
    from sueldos.service import Scope, SueldosService

    @contextmanager
    def tx():
        with db_conn.transaction():
            yield db_conn

    svc = SueldosService(None, None, None, today=lambda: HOY, transaction=tx)
    iguales = por_diseno = 0
    for inst, dep, pid in _abiertos(db_conn):
        scope = Scope(inst, dep, {"id": inst}, {"id": dep}, "superadmin")
        nombre = db_conn.execute("SELECT nombre FROM periodos WHERE id = %s", [pid]).fetchone()[0]
        for tipo in ("investigacion", "extension"):
            det = svc.costos_proyectos_vigentes(scope, tipo)["detalle"]
            for _, a in (det if det is not None else pd.DataFrame()).iterrows():
                r = svc.sueldo_docente_resumen(scope, a["cuil"], {"id": pid, "nombre": nombre})
                total = r["total"] if r["estado"] == "ok" else 0.0
                if round(float(a["sueldo_mensual_docente_v257"]), 2) == round(total, 2):
                    iguales += 1
                    continue
                deps = db_conn.execute(
                    "SELECT count(DISTINCT d.departamento_id) FROM designaciones d JOIN periodos p ON p.id = d.periodo_id "
                    "WHERE d.institucion_id = %s AND regexp_replace(d.cuil, '[^0-9]', '', 'g') = "
                    "regexp_replace(%s, '[^0-9]', '', 'g') AND p.nombre = %s AND COALESCE(d.estado, 'Activa') = 'Activa'",
                    [inst, a["cuil"], nombre]).fetchone()[0]
                assert deps > 1, ("diferencia sin explicar", dep, tipo, int(a["id"]))
                por_diseno += 1
    assert iguales >= 700 and por_diseno <= 30


# ------------------------------------------------------------------------------------------ B4
@pytest.mark.parametrize("encabezado,clave", [
    ("Años antigüedad", "anos_antiguedad"), ("AÑOS ANTIGÜEDAD", "anos_antiguedad"), ("  años  antigüedad ", "anos_antiguedad"),
    ("Antigüedad", "antiguedad"), ("N° resolución", "n_resolucion"), ("Nº resolución", "n_resolucion"),
    ("N.° resolución", "n_resolucion"), ("n° de resolución", "n_de_resolucion"), ("Título posgrado", "titulo_posgrado"),
    ("Dedicación", "dedicacion"), ("Período", "periodo"), ("Ref. legajo físico", "ref_legajo_fisico"),
    ("Fecha-desde", "fecha_desde"), ("Teléfono", "telefono"),
])
def test_b4_normalizador_reconoce_variantes(encabezado, clave):
    from docentes.carga import normalizar_columna_generica
    assert normalizar_columna_generica(encabezado) == clave


def _alias_y_modelos() -> set:
    import re
    from pathlib import Path
    base = Path(__file__).resolve().parents[1]
    textos = set()
    for rel in ("docentes/carga.py", "designaciones/rules.py", "comisiones/carga.py",
                "integraciones/carga_integral_motor/complemento.py", "designaciones/excel.py", "comisiones/excel.py"):
        textos |= set(re.findall(r'"([^"\n]{1,40})"', (base / rel).read_text(encoding="utf-8")))
    return textos


def test_b4_sin_cambios_para_lo_que_el_certificado_ya_reconocia():
    from analisis.motor.ref.extracted_batch01.otros import normalizar_columna_generica as certificado
    from docentes.carga import normalizar_columna_generica as nuevo
    distintos = [t for t in _alias_y_modelos() if certificado(t) != nuevo(t)]
    # solo cambian los textos con diacriticos fuera de á é í ó ú ñ o con ° / º (antes nunca coincidian con un alias)
    assert all(any(ch in t for ch in "üÜ°ºàèìòùçÀÈÌÒÙÇ") for t in distintos), distintos
    assert {certificado("Años antigüedad"), certificado("N° resolución")} == {"anos_antigüedad", "n°_resolucion"}


def test_b4_sin_colisiones_entre_campos():
    """Cada alias conocido de Docentes y Designaciones sigue yendo a UN solo campo canonico."""
    from designaciones.rules import normalizar_columnas_designaciones_pegadas
    from docentes.carga import normalizar_columnas_docentes_pegados
    for fn in (normalizar_columnas_docentes_pegados, normalizar_columnas_designaciones_pegadas):
        for t in sorted(_alias_y_modelos()):
            out = fn(pd.DataFrame([["v"]], columns=[t]))
            assert int((out.astype(str) == "v").sum().sum()) <= 1, (fn.__name__, t)


# ------------------------------------------------------------------------------------------ B5
def _cabecera(data: bytes, hoja=None) -> list:
    wb = load_workbook(BytesIO(data))
    ws = wb[hoja] if hoja else wb.worksheets[0]
    return [c.value for c in ws[1] if c.value is not None]


def _perdidos(cab: list, fn) -> list:
    df = pd.DataFrame([[f"v{i}" for i in range(len(cab))]], columns=cab)
    vals = set(fn(df).astype(str).values.ravel())
    return [h for i, h in enumerate(cab) if f"v{i}" not in vals]


def test_b5_modelos_docentes_y_designaciones_se_releen():
    from designaciones import excel as DE
    from designaciones.rules import normalizar_columnas_designaciones_pegadas
    from docentes import carga as DC
    assert _perdidos(_cabecera(DC.generar_excel_modelo_carga_rapida_docentes()), DC.normalizar_columnas_docentes_pegados) == []
    cab = _cabecera(DE.generar_excel_modelo_carga_rapida_designaciones([], [], None))
    assert "N° resolución" in cab
    assert _perdidos(cab, normalizar_columnas_designaciones_pegadas) == ["Docente"]  # informativa (formula por CUIL)


def test_b5_modelo_comisiones_se_relee():
    import re
    from pathlib import Path
    from comisiones.carga import normalizar_columnas_comisiones_pegadas
    src = (Path(__file__).resolve().parents[1] / "comisiones" / "excel.py").read_text(encoding="utf-8")
    i = src.index("    encabezados = [", src.index("def generar_excel_modelo_carga_rapida_comisiones"))
    cab = re.findall(r'"([^"]+)"', src[i:src.index("]", i)])
    assert len(cab) == 29 and _perdidos(cab, normalizar_columnas_comisiones_pegadas) == []


@pytest.mark.parametrize("modulo", ["investigacion", "extension"])
def test_b5_modelo_de_proyectos_round_trip(modulo):
    X = __import__(f"{modulo}.excel", fromlist=["x"])
    wb = load_workbook(BytesIO(X.modelo_v127(pd.DataFrame())))
    ws = wb["Carga rápida"]
    cab = [c.value for c in ws[1] if c.value]
    for i in range(len(cab)):
        ws.cell(2, i + 1).value = f"v{i}"
    out = BytesIO()
    wb.save(out)
    df = X.leer_carga_rapida_v127(out.getvalue())
    vals = set(df.astype(str).values.ravel())
    assert [h for i, h in enumerate(cab) if f"v{i}" not in vals] == []


# ------------------------------------------------------------------------------------------ B11 cross-module
@pytest.mark.parametrize("dep", [1, 2, 3, 4, 9])
def test_b11_resumen_cross_module_contra_sql_independiente(auth_db, audit_store, db_conn, dep):
    """Docentes -> Designaciones -> Investigacion/Extension -> Comisiones -> Sueldos -> Resumen, de punta a punta, con el
    servicio real del Resumen (E4-05) y verificaciones INDEPENDIENTES (SQL propio) para cada docente de la muestra
    (una categoria por departamento: comisiones, investigacion, extension, compartido, Ad Honorem, prestado, ...)."""
    from test_e4_02_plantel import superadmin_en
    from test_e4_05_resumen import candidatos, make_resumen
    svc = make_resumen(auth_db, audit_store, db_conn)
    record, _ = superadmin_en(auth_db, db_conn, 1, dep)
    dig = "regexp_replace(COALESCE({c}, ''), '[^0-9]', '', 'g')"
    verificados = 0
    for categoria, cuil in candidatos(db_conn, 1, dep).items():
        r = svc.resumen(record, cuil)
        per = r["seleccionado"]
        if per is None:
            continue
        nombre = per["nombre"]
        s = r["secciones"]
        # Designaciones: todas de la institucion de la sesion y del periodo (equivalente); todas las Activas del
        # departamento de la sesion presentes
        t = s["designaciones"]["tabla"]
        ids = {int(f[t["columnas"].index("id")]) for f in t["filas"]} if t else set()
        if ids:
            fuera = db_conn.execute("SELECT count(*) FROM designaciones d JOIN periodos p ON p.id = d.periodo_id WHERE "
                                    "d.id = ANY(%s) AND (d.institucion_id <> 1 OR p.nombre <> %s)", [list(ids), nombre]).fetchone()[0]
            assert fuera == 0, (categoria, "designacion ajena")
        locales = {x[0] for x in db_conn.execute(
            f"SELECT d.id FROM designaciones d WHERE d.institucion_id = 1 AND d.departamento_id = %s AND d.periodo_id = %s "
            f"AND d.estado = 'Activa' AND {dig.format(c='d.cuil')} = {dig.format(c='%s')}", [dep, per["id"], cuil])}
        assert locales <= ids, (categoria, "falta una designacion Activa local")
        # Comisiones: asignaciones Activas del docente en comisiones del periodo (institucion)
        t = s["comisiones"]["tabla"]
        n_com = len(t["filas"]) if t else 0
        esperado = db_conn.execute(
            f"SELECT count(*) FROM asignaciones_docentes_comision a JOIN comisiones co ON co.id = a.comision_id "
            f"JOIN periodos p ON p.id = co.periodo_id WHERE a.institucion_id = 1 AND p.nombre = %s AND "
            f"COALESCE(a.estado, 'Activa') = 'Activa' AND {dig.format(c='a.cuil')} = {dig.format(c='%s')}",
            [nombre, cuil]).fetchone()[0]
        assert n_com <= esperado and (esperado == 0) == (n_com == 0), (categoria, "comisiones", n_com, esperado)
        # Investigacion / Extension: asignaciones activas del docente (institucion, periodo equivalente)
        for tabla, clave in (("investigacion_docente", "investigacion"), ("extension_docente", "extension")):
            esperado = db_conn.execute(
                f"SELECT count(*) FROM {tabla} x JOIN periodos p ON p.id = x.periodo_id WHERE x.institucion_id = 1 AND "
                f"p.nombre = %s AND COALESCE(x.estado_asignacion, 'Activa') = 'Activa' AND "
                f"{dig.format(c='x.cuil')} = {dig.format(c='%s')}", [nombre, cuil]).fetchone()[0]
            t = s[clave]["tabla"]
            assert (t is not None and len(t["filas"]) > 0) == (esperado > 0), (categoria, clave, esperado)
        # Sueldo: calculo independiente (B1)
        scope = svc.sueldos.scope(record)
        crudo = svc.sueldos.sueldo_docente_resumen(scope, cuil, per)
        if crudo["estado"] == "ok":
            ind = sueldo_resumen_independiente(db_conn, 1, dep, cuil, int(per["id"]), crudo["mes_objetivo"], FIXED_TODAY)
            assert crudo["total"] == ind["total"], (categoria, "sueldo")
        verificados += 1
    assert verificados >= 5


def test_b2_antiguedad_y_posgrado_de_la_ficha_en_el_resumen(auth_db, audit_store, db_conn):
    """B1/B2: con la ficha informada (sintetico dentro de la transaccion, ROLLBACK), "Datos generales" y el sueldo del
    Resumen usan la MISMA antiguedad y posgrado de la ficha (el certificado mostraba "no informada" / 0 anios)."""
    from test_e4_02_plantel import superadmin_en
    from test_e4_05_resumen import make_resumen
    cuil = db_conn.execute("SELECT d.cuil FROM designaciones d WHERE d.institucion_id = 1 AND d.departamento_id = 1 "
                           "AND d.periodo_id = 9 AND d.estado = 'Activa' AND d.ad_honorem = 'No' ORDER BY d.cuil LIMIT 1"
                           ).fetchone()[0]
    db_conn.execute("UPDATE docentes SET antiguedad_anios = 12, nivel_posgrado_salarial = 'Doctora' WHERE "
                    "institucion_id = 1 AND departamento_id = 1 AND cuil = %s", [cuil])
    svc = make_resumen(auth_db, audit_store, db_conn)
    record, _ = superadmin_en(auth_db, db_conn, 1, 1)
    r = svc.resumen(record, cuil, 9)
    f = r["secciones"]["datos_generales"]["formacion"]
    assert f["antiguedad"] == "**Antigüedad:** 12 años" and f["nivel"] == "Doctor"
    su = r["secciones"]["sueldo"]
    assert "Antigüedad aplicada: **12 años" in su["caption"] and "Posgrado: **Doctor" in su["caption"]
    t = su["tabla"]
    assert {fila[t["columnas"].index("Antigüedad")] for fila in t["filas"]} == {"12 años (" + t["filas"][0][
        t["columnas"].index("Antigüedad")].split("(")[1]}
