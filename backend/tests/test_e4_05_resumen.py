"""E4-05 — Docentes: pestaña "📊 Resumen docente" (lectura).

Diferencial contra B13-FIX02: la pestaña LITERAL (``with tab5:`` l. 60845, cortada antes de la seccion E4-06) ejecutada
con un Streamlit grabador sobre el namespace certificado construido desde reference_fix02 (``e4_05_support``), contra
``ResumenDocenteService`` (motor de Analisis + complemento + owners Sueldos/Actividades).  Se compara la secuencia
COMPLETA de llamadas desde "### Datos generales" hasta "Materias históricas" (textos, avisos, metricas, tablas, torta,
tarjeta y cronograma), mas la cabecera y el selector de periodo.  Docentes elegidos por categoria en cada departamento
(muchas comisiones, investigacion, extension, actividades especiales, sin designaciones, compartido, prestado,
Ad Honorem) en el periodo por defecto y en el historico.  Datos reales de deptit_next_dev; todo se revierte.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from comisiones_support import FIXED_NOW
from e4_05_support import _segmento_sueldo, certificado, certified_resumen, comparar, normalizar
from periodos_support import FIXED_TODAY, audit_store, db_conn, savepoint  # noqa: F401
from saas_support import auth_db, ids_por_rol, nueva_institucion, nuevo_departamento, sesion  # noqa: F401
from test_e4_02_plantel import departamentos_con_periodos, superadmin_en

from actividades_especiales.service import ActividadesService
from docentes.service import DocentesError, DocentesService
from integraciones.resumen_docente import ADVERTENCIA_ESTIMACION, ResumenDocenteService
from sueldos.service import SueldosService

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning", "ignore::DeprecationWarning")

BACKEND = Path(__file__).resolve().parents[1]
SECCIONES = ["designaciones", "actos", "sueldo", "investigacion", "extension", "actividades", "comisiones",
             "superposiciones", "materias_historicas"]


def make_resumen(auth, audit_store, db_conn):
    kw = dict(today=lambda: FIXED_TODAY, transaction=lambda: savepoint(db_conn))
    return ResumenDocenteService(
        None, auth, DocentesService(None, auth, None, **kw), SueldosService(None, auth, audit_store, **kw),
        ActividadesService(None, auth, audit_store, now=lambda: FIXED_NOW, **kw), now=lambda: FIXED_NOW, **kw)


def verificador(svc, record, db_conn, cuil):
    """B1: la seccion de sueldo del Resumen NEXT = calculo independiente (``e5_b_support``) para el periodo mostrado."""
    from e5_b_support import filas_next, sueldo_resumen_independiente
    from sueldos import rules as SR

    def verificar(r) -> bool:
        per = r["seleccionado"]
        scope = svc.sueldos.scope(record)
        crudo = svc.sueldos.sueldo_docente_resumen(scope, cuil, per)
        esperado = sueldo_resumen_independiente(db_conn, scope.institution_id, scope.department_id, cuil,
                                                int(per["id"]), crudo["mes_objetivo"], FIXED_TODAY)
        assert filas_next(crudo) == esperado["filas"] and crudo["total"] == esperado["total"]
        tabla = r["secciones"]["sueldo"]["tabla"]
        mostradas = sorted((f[tabla["columnas"].index("Cargo")], f[tabla["columnas"].index("Sueldo estimado")])
                           for f in tabla["filas"])
        assert mostradas == sorted((c, SR.moneda_v256(v)) for c, _, _, v in esperado["filas"])
        assert r["secciones"]["sueldo"]["total"]["valor"] == SR.moneda_v256(esperado["total"])
        return True
    return verificar


def _uno(conn, sql, params):
    fila = conn.execute(sql, params).fetchone()
    return None if fila is None else fila[0]


def candidatos(conn, inst, dep) -> dict:
    """Un docente del departamento (base maestra) por categoria, para el periodo abierto del departamento."""
    pid = _uno(conn, "SELECT id FROM periodos WHERE institucion_id=%s AND departamento_id=%s AND estado='Abierto' "
                     "ORDER BY id DESC LIMIT 1", [inst, dep])
    nombre = _uno(conn, "SELECT nombre FROM periodos WHERE id=%s", [pid]) if pid else None
    base = "SELECT d.cuil FROM docentes d WHERE d.institucion_id=%s AND d.departamento_id=%s AND d.cuil IS NOT NULL "
    q = {
        "comisiones": base + "AND d.cuil IN (SELECT a.cuil FROM asignaciones_docentes_comision a JOIN comisiones co ON "
                             "co.id=a.comision_id JOIN periodos p ON p.id=co.periodo_id WHERE p.nombre=%s) "
                             "ORDER BY (SELECT count(*) FROM asignaciones_docentes_comision a2 WHERE a2.cuil=d.cuil) "
                             "DESC, d.cuil LIMIT 1",
        "investigacion": base + "AND d.cuil IN (SELECT i.cuil FROM investigacion_docente i JOIN periodos p ON "
                                "p.id=i.periodo_id WHERE p.nombre=%s) ORDER BY d.cuil LIMIT 1",
        "extension": base + "AND d.cuil IN (SELECT e.cuil FROM extension_docente e JOIN periodos p ON "
                            "p.id=e.periodo_id WHERE p.nombre=%s) ORDER BY d.cuil LIMIT 1",
        "actividades": base + "AND d.cuil IN (SELECT a.cuil FROM actividad_especial_docente a JOIN periodos p ON "
                              "p.id=a.periodo_id WHERE p.nombre=%s) ORDER BY d.cuil LIMIT 1",
        "sin_designaciones": base + "AND d.cuil NOT IN (SELECT x.cuil FROM designaciones x JOIN periodos p ON "
                                    "p.id=x.periodo_id WHERE p.nombre=%s AND x.cuil IS NOT NULL) ORDER BY d.cuil LIMIT 1",
        "compartido": base + "AND d.cuil IN (SELECT x.cuil FROM designaciones x JOIN periodos p ON p.id=x.periodo_id "
                             "WHERE p.nombre=%s GROUP BY x.cuil HAVING count(DISTINCT x.departamento_id) > 1) "
                             "ORDER BY d.cuil LIMIT 1",
        "ad_honorem": base + "AND d.cuil IN (SELECT x.cuil FROM designaciones x JOIN periodos p ON p.id=x.periodo_id "
                             "WHERE p.nombre=%s AND x.ad_honorem='Sí') ORDER BY d.cuil LIMIT 1",
    }
    out = {k: _uno(conn, v, [inst, dep, nombre]) for k, v in q.items()} if nombre else {}
    out["prestado"] = _uno(conn, "SELECT cuil FROM prestamos_docentes WHERE institucion_id=%s AND departamento_id=%s "
                                 "ORDER BY id LIMIT 1", [inst, dep])
    return {k: v for k, v in out.items() if v}


def _cubiertas(r: dict, cobertura: dict):
    s = r["secciones"]
    for k in SECCIONES:
        cobertura.setdefault(k, 0)
        cobertura[k] += s[k]["tabla"] is not None
    t = s["tarjeta"]
    for k in ("aviso_prestado", "compartido", "funciones_no_docentes", "evolucion", "estado_designacion"):
        cobertura.setdefault(f"tarjeta.{k}", 0)
        cobertura[f"tarjeta.{k}"] += bool(t[k])
    cobertura.setdefault("cronograma", 0)
    cobertura["cronograma"] += any(c for f in s["cronograma"]["filas"] for c in f["celdas"])
    cobertura.setdefault("torta", 0)
    cobertura["torta"] += s["productividad"]["torta"] is not None
    cobertura.setdefault("detalle_no_lectivas", 0)
    cobertura["detalle_no_lectivas"] += s["productividad"]["detalle_no_lectivas"] is not None
    cobertura.setdefault("observaciones", 0)
    cobertura["observaciones"] += bool(s["datos_generales"]["observaciones"])


# ------------------------------------------------------------------------------------------ diferencial
@pytest.mark.parametrize("dep", [1, 2, 4, 9])
def test_diferencial_por_categoria_y_periodo(auth_db, audit_store, db_conn, dep):
    inst = 1
    svc = make_resumen(auth_db, audit_store, db_conn)
    record, _ = superadmin_en(auth_db, db_conn, inst, dep)
    ns = certified_resumen(db_conn, inst, dep)
    cand = candidatos(db_conn, inst, dep)
    assert len(cand) >= 4
    periodos = [p for p in svc.resumen(record, next(iter(cand.values())))["periodos"]]
    comparados, cobertura = 0, {}
    for categoria, cuil in cand.items():
        r = svc.resumen(record, cuil)
        assert r["estimacion"]["advertencia"] == ADVERTENCIA_ESTIMACION
        assert len(comparar(certificado(ns, cuil), r, verificador(svc, record, db_conn, cuil))) == 13, categoria
        _cubiertas(r, cobertura)
        comparados += 1
    for p in periodos:  # cada periodo (actual e historico) para el docente con mas comisiones
        cuil = cand.get("comisiones") or next(iter(cand.values()))
        r = svc.resumen(record, cuil, p["id"])
        assert r["seleccionado"] == p
        comparar(certificado(ns, cuil, p["nombre"]), r, verificador(svc, record, db_conn, cuil))
        comparados += 1
    assert comparados >= 5


def test_cobertura_de_secciones_en_todos_los_departamentos(auth_db, audit_store, db_conn):
    """Cada seccion con datos (no solo el mensaje vacio) aparece al menos una vez, igual al certificado."""
    svc = make_resumen(auth_db, audit_store, db_conn)
    cobertura: dict = {}
    for inst, dep in departamentos_con_periodos(db_conn):
        cand = candidatos(db_conn, inst, dep)
        if not cand:
            continue
        record, _ = superadmin_en(auth_db, db_conn, inst, dep)
        for cuil in cand.values():
            _cubiertas(svc.resumen(record, cuil), cobertura)
    faltan = [k for k, v in cobertura.items() if v == 0 and k not in ("tarjeta.funciones_no_docentes",
                                                                       "tarjeta.estado_designacion")]
    assert not faltan, faltan


def test_ad_honorem_en_el_resumen_corregido_b1(auth_db, audit_store, db_conn):
    """D-E4-02 / H2: en el Resumen certificado la fuente v149 no trae ``ad_honorem`` y la designacion Ad Honorem se
    valoriza como rentada (caso real dep 1, 2026-2: Titular Simple $ 584.573,72).  Etapa 5 / Tanda B (B1): NEXT la
    corrige ($ 0,00, como el plantel y el caption certificado); el resto del Resumen sigue identico."""
    cuil = db_conn.execute("""SELECT d.cuil FROM designaciones d WHERE d.institucion_id=1 AND d.departamento_id=1
        AND d.periodo_id=9 AND d.ad_honorem='Sí' AND d.estado='Activa' AND d.cargo='Titular' AND d.dedicacion='Simple'
        ORDER BY d.cuil LIMIT 1""").fetchone()[0]
    svc = make_resumen(auth_db, audit_store, db_conn)
    record, _ = superadmin_en(auth_db, db_conn, 1, 1)
    r = svc.resumen(record, cuil, 9)
    cert = certificado(certified_resumen(db_conn, 1, 1), cuil, "2026-2")
    norm = normalizar(cert)
    i, j = _segmento_sueldo(norm)
    tabla_c = next(e[1] for e in norm[i:j] if e[0] == "dataframe")
    fila_c = [dict(zip(tabla_c["columnas"], f)) for f in tabla_c["filas"]]
    assert [f for f in fila_c if f["Cargo"] == "Titular" and f["Dedicación"] == "Simple" and f["Ad Honorem"] == "No"
            and f["Sueldo estimado"] == "$ 584.573,72"]  # anomalia certificada H2
    comparar(cert, r, verificador(svc, record, db_conn, cuil))
    tabla = r["secciones"]["sueldo"]["tabla"]
    filas = [dict(zip(tabla["columnas"], f)) for f in tabla["filas"]]
    titular = [f for f in filas if f["Cargo"] == "Titular" and f["Dedicación"] == "Simple"]
    assert titular and titular[0]["Ad Honorem"] == "Sí" and titular[0]["Sueldo estimado"] == "$ 0,00"  # NEXT (B1)


def test_tarjeta_funcion_no_docente_y_suspendida(auth_db, audit_store, db_conn):
    """Variantes de la tarjeta sin datos reales suficientes: funciones no docentes (tabla + caption) y estado
    "Suspendida (licenciada)".  Designaciones sinteticas de un docente real, dentro de la transaccion (ROLLBACK)."""
    cuil = db_conn.execute("""SELECT cuil FROM designaciones WHERE institucion_id=1 AND departamento_id=1 AND periodo_id=9
        AND estado='Activa' AND COALESCE(ad_honorem,'No')='No' ORDER BY cuil LIMIT 1""").fetchone()[0]
    for cargo, estado, fnd, texto in (("JTP", "Suspendida", 0, ""), ("Ayudante 1ra", "Activa", 1,
                                                                         "Coordinación ZZNEXT de laboratorio")):
        db_conn.execute("INSERT INTO designaciones (institucion_id, departamento_id, periodo_id, cuil, cargo, dedicacion, "
                        "horas, tipo_designacion, ad_honorem, fecha_desde, estado, funcion_no_docente, "
                        "texto_funcion_no_docente) VALUES (1,1,9,%s,%s,'Simple',10,'Interino','No','2026-08-01',%s,%s,%s)",
                        [cuil, cargo, estado, fnd, texto])
    svc = make_resumen(auth_db, audit_store, db_conn)
    record, _ = superadmin_en(auth_db, db_conn, 1, 1)
    r = svc.resumen(record, cuil, 9)
    comparar(certificado(certified_resumen(db_conn, 1, 1), cuil, "2026-2"), r, verificador(svc, record, db_conn, cuil))
    t = r["secciones"]["tarjeta"]
    assert t["estado_designacion"] == "Estado de la designación: **Suspendida (licenciada)**"
    assert t["funciones_no_docentes"] and "Coordinación ZZNEXT de laboratorio" in str(t["funciones_no_docentes"])


def test_departamento_sin_periodos_y_sin_docentes(auth_db, audit_store, db_conn):
    inst = nueva_institucion(db_conn, nombre="ZZNEXT E4-05 Instituto")
    dep = nuevo_departamento(db_conn, inst, nombre="ZZNEXT E4-05 Depto")
    svc = make_resumen(auth_db, audit_store, db_conn)
    record, _ = superadmin_en(auth_db, db_conn, inst, dep)
    assert svc.resumen(record, "20-00000000-1")["sin_docentes"] == "Todavía no hay docentes registrados."
    db_conn.execute("INSERT INTO docentes (institucion_id, departamento_id, cuil, apellido, nombres, estado) "
                    "VALUES (%s,%s,'20-90000555-5','Zeta','Uno','Activo')", [inst, dep])
    assert svc.resumen(record, "20-90000555-5")["sin_periodos"] == "Todavía no hay períodos registrados."


# ------------------------------------------------------------------------------------------ roles, scope, validacion
def test_roles_scope_y_ids_manipulados(auth_db, audit_store, db_conn):
    svc = make_resumen(auth_db, audit_store, db_conn)
    ids = ids_por_rol(db_conn)
    record, _ = sesion(auth_db, ids["usuario_departamento"])
    propio = auth_db.resolve_scope(record).department["id"]
    with db_conn.cursor() as cur:
        cur.execute("SELECT cuil FROM docentes WHERE institucion_id=1 AND departamento_id=%s ORDER BY cuil LIMIT 1",
                    [propio])
        mio = cur.fetchone()[0]
        cur.execute("SELECT d.cuil FROM docentes d WHERE d.institucion_id=1 AND d.departamento_id<>%s AND NOT EXISTS "
                    "(SELECT 1 FROM docentes x WHERE x.departamento_id=%s AND x.cuil=d.cuil) ORDER BY d.cuil LIMIT 1",
                    [propio, propio])
        ajeno = cur.fetchone()[0]
        cur.execute("SELECT id FROM periodos WHERE departamento_id<>%s ORDER BY id LIMIT 1", [propio])
        periodo_ajeno = cur.fetchone()[0]
    assert svc.resumen(record, mio)["secciones"]
    for cuil, status in ((ajeno, 404), ("", 422), (None, 422), (123, 422)):
        with pytest.raises(DocentesError) as exc:
            svc.resumen(record, cuil)
        assert exc.value.status == status
    for pid, status in ((periodo_ajeno, 404), ("9", 422), (True, 422)):
        with pytest.raises(DocentesError) as exc:
            svc.resumen(record, mio, pid)
        assert exc.value.status == status
    coord, _ = sesion(auth_db, ids["coordinador_institucional"])
    with pytest.raises(DocentesError) as exc:
        svc.resumen(coord, mio)
    assert exc.value.status == 409


# ------------------------------------------------------------------------------------------ HTTP y seguridad
@pytest.fixture
def http(auth_db, audit_store, db_conn):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from auth.routes import router as auth_router
    from integraciones.routes import docentes_router

    app = FastAPI()
    app.state.auth = auth_db
    app.state.resumen_docente = make_resumen(auth_db, audit_store, db_conn)
    app.include_router(auth_router)
    app.include_router(docentes_router)
    return TestClient(app, base_url="http://localhost")


def test_http_csrf_sesion_y_respuesta_limpia(http, auth_db, db_conn):
    csrf = {"X-DEPTIT-Request": "1"}
    cuil = db_conn.execute("SELECT cuil FROM docentes WHERE institucion_id=1 AND departamento_id=1 ORDER BY cuil "
                           "LIMIT 1").fetchone()[0]
    assert http.post("/docentes/resumen", json={"cuil": cuil}, headers=csrf).status_code == 401
    _, token = superadmin_en(auth_db, db_conn, 1, 1)
    http.cookies.set("deptit_session", token)
    assert http.post("/docentes/resumen", json={"cuil": cuil}).status_code == 403
    assert http.get("/docentes/resumen").status_code == 405
    r = http.post("/docentes/resumen", json={"cuil": cuil, "departamento_id": 2, "sql": "x"}, headers=csrf)
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    # E4-06 reemplazó el aviso "pendiente_e406" por la sección real "consulta"
    assert {"subtitulo", "info", "periodos", "seleccionado", "secciones", "estimacion", "consulta"} <= set(r.json())
    assert not re.search(r"(?i)select\s|traceback|psycopg|C:\\\\|password|salt", r.text)
    assert http.post("/docentes/resumen", json={"cuil": "20-99999999-9"}, headers=csrf).status_code == 404


# ------------------------------------------------------------------------------------------ arquitectura
def test_composicion_solo_lectura_y_sin_ciclos():
    for nombre in ("resumen_docente.py", "resumen_pagina.py", "resumen_horas.py"):
        codigo = re.sub(r'"""[\s\S]*?"""', "", (BACKEND / "integraciones" / nombre).read_text(encoding="utf-8"))
        assert not re.search(r"(?i)\b(INSERT|UPDATE|DELETE|AuditStore|commit)\b", codigo)
    assert "SET TRANSACTION READ ONLY" in (BACKEND / "integraciones" / "resumen_docente.py").read_text(encoding="utf-8")
    from integraciones.resumen_motor import metadata
    assert metadata.WRITERS_NEGOCIO == [] and metadata.TAREAS_SISTEMA == {}
    complemento = (BACKEND / "integraciones" / "resumen_motor" / "complemento.py").read_text(encoding="utf-8")
    assert "guardar_estado_consulta_designacion" not in complemento  # writer de E4-06: fuera
    assert "generar_mensaje_consulta_designacion_docente" not in complemento
    for paquete in ("docentes", "sueldos", "actividades_especiales", "analisis"):
        src = "\n".join(p.read_text(encoding="utf-8") for p in (BACKEND / paquete).glob("*.py"))
        assert not re.search(r"^\s*(from|import)\s+integraciones\b", src, re.M)


def test_complemento_es_literal_del_entry():
    """Cada bloque del complemento es texto literal del entry (sin decoradores) en su linea de origen."""
    from periodos_support import ENTRY
    entry = ENTRY.read_text(encoding="utf-8").splitlines()
    texto = (BACKEND / "integraciones" / "resumen_motor" / "complemento.py").read_text(encoding="utf-8")
    bloques = re.findall(r"# --- entry l\. (\d+)-(\d+)\n(.*?)(?=\n\n# --- entry|\Z)", texto, re.S)
    assert len(bloques) >= 18
    for a, b, cuerpo in bloques:
        original = "\n".join(entry[int(a) - 1:int(b)])
        assert cuerpo.strip().replace("analisis.motor.ref", "deptit_refactor") == original.strip()
