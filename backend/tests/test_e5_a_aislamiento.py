"""Etapa 5 / Tanda A — tests negativos transversales de seguridad, ambito e integridad.

- ``DQ-SCOPE-OR-B12B``: el hardening central ``analisis.motor.ambito.proteger_or`` (identidad sin OR de nivel
  superior, envoltura correcta, fail closed), su aplicacion en los DOS entornos que ejecutan el inyector B12B (motor de
  lectura: Analisis / Inicio / Resumen docente / carga integral; motor de Periodos), la fuga real bloqueada sobre la base
  (sintetico + ROLLBACK) y la clasificacion fija de cada SQL certificado con OR de nivel superior (un SQL nuevo con OR
  sin clasificar hace fallar este test).
- A4: TODAS las rutas del backend exigen sesion (sin sesion -> 401 sin tocar ningun servicio) y toda ruta que no es GET
  exige la cabecera CSRF (-> 403 sin tocar ningun servicio); ningun body fuera de Auth/SaaS define institucion ni
  departamento; los proxies Next solo exponen rutas existentes del backend y validan el mismo origen en cada POST propio.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd
import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from analisis.motor import entorno
from analisis.motor.ambito import AmbitoNoGarantizable, or_nivel_superior, proteger_or, proteger_subconsultas
from analisis_support import db_conn, motor  # noqa: F401

BACKEND = Path(__file__).resolve().parents[1]
FRONT_API = BACKEND.parent / "frontend" / "src" / "app" / "api"
TENANT = {"kind": "tenant", "institucion_id": 1, "departamento_id": 1}
SQL_ANTERIOR = ("SELECT id FROM periodos WHERE (anio < ?) OR (anio = ? AND semestre < ?) "
                "ORDER BY anio DESC, semestre DESC, id DESC LIMIT 1")


# ------------------------------------------------------------------------------------------ proteger_or
@pytest.mark.parametrize("sql", [
    "SELECT id FROM periodos WHERE anio = ? AND semestre = ?",
    "SELECT id FROM docentes WHERE estado = 'Activo' AND (cuil = ? OR legajo = ?)",
    "SELECT id FROM docentes WHERE nombre = 'A OR B'",
    "SELECT id FROM designaciones WHERE periodo_id IN (SELECT id FROM periodos WHERE anio = 1 OR anio = 2)",
    "SELECT COUNT(*) FROM movimientos",
    "WITH x AS (SELECT id FROM periodos WHERE a = 1 OR b = 2) SELECT id FROM x WHERE id > 0",
])
def test_sin_or_de_nivel_superior_el_sql_queda_identico(sql):
    assert not or_nivel_superior(sql)
    assert proteger_or(sql) == sql


def test_or_de_nivel_superior_se_envuelve_y_conserva_el_resto():
    assert proteger_or(SQL_ANTERIOR) == ("SELECT id FROM periodos WHERE ((anio < ?) OR (anio = ? AND semestre < ?)) "
                                         "ORDER BY anio DESC, semestre DESC, id DESC LIMIT 1")
    assert proteger_or("UPDATE investigacion_docente SET x = 1 WHERE a IS NULL OR TRIM(a) = ''") == (
        "UPDATE investigacion_docente SET x = 1 WHERE (a IS NULL OR TRIM(a) = '')")
    assert proteger_or("SELECT a FROM t WHERE x = 'a OR b' AND y = 1 OR z = 2") == (
        "SELECT a FROM t WHERE (x = 'a OR b' AND y = 1 OR z = 2)")


def test_or_no_envolvible_falla_cerrado():
    with pytest.raises(AmbitoNoGarantizable):
        proteger_or("SELECT id FROM periodos WHERE a = 1 OR b = 2 UNION SELECT id FROM periodos WHERE c = 3")


def test_inyector_certificado_sigue_literal_y_con_la_anomalia():
    """El inyector vendorizado NO se modifica (texto literal): la anomalia sigue ahi y la corrige el entorno."""
    crudo = entorno._inyector()["_pg_scope_select"](SQL_ANTERIOR, [2026, 2026, 1], TENANT)[0]
    assert "WHERE (anio < %s) OR (anio = %s AND semestre < %s) AND (periodos.institucion_id = %s)" in crudo


@pytest.mark.parametrize("ambito", [TENANT, {"kind": "planes", "institucion_id": 1}])
def test_motor_de_lectura_protege_el_or(ambito):
    sql = "SELECT id FROM proyectos_investigacion WHERE fecha_inicio IS NULL OR fecha_fin IS NULL"
    q, p = entorno._Conexion(None, ambito).preparar(sql, [])
    assert q.startswith("SELECT id FROM proyectos_investigacion WHERE (fecha_inicio IS NULL OR fecha_fin IS NULL) AND ")
    assert not or_nivel_superior(q) and p == [1]


def test_motor_de_lectura_sin_or_identico_al_certificado():
    sql = "SELECT d.id FROM designaciones d LEFT JOIN docentes x ON x.cuil = d.cuil WHERE d.periodo_id = ?"
    assert entorno._Conexion(None, TENANT).preparar(sql, [9]) == entorno._inyector()["_pg_scope_select"](sql, [9], TENANT)


def test_motor_de_periodos_protege_el_or():
    from integraciones.ciclo_periodos.entorno import _TenantConn
    q, _ = _TenantConn(None, TENANT).preparar(SQL_ANTERIOR, [2026, 2026, 1])
    assert "WHERE ((anio < %s) OR (anio = %s AND semestre < %s)) AND (periodos.institucion_id = %s)" in q


def test_fuga_real_bloqueada_en_el_motor_de_lectura(db_conn):
    """Sintetico (ROLLBACK): un periodo 1990 de OTRO tenant (inst 2 / dep 5).  Con el inyector certificado sin
    proteccion, ``get_periodo_anterior_cronologico`` del primer periodo del dep 1 devuelve ese periodo ajeno; con el
    entorno NEXT, nada fuera del departamento de la sesion."""
    from analisis.motor.ref.extracted_batch03.readonly_queries import get_periodo_anterior_cronologico as anterior
    ajeno = db_conn.execute("INSERT INTO periodos (institucion_id, departamento_id, nombre, anio, semestre, estado) "
                            "VALUES (2, 5, 'ZZE5 1990-1', 1990, 1, 'Cerrado') RETURNING id").fetchone()[0]
    propios = {r[0]: (r[1], r[2]) for r in db_conn.execute(
        "SELECT id, anio, semestre FROM periodos WHERE institucion_id = 1 AND departamento_id = 1")}
    primero = min(propios, key=lambda k: propios[k])
    ns = motor(db_conn, 1, 1)

    class SinProteccion(entorno._Conexion):
        def preparar(self, sql, params):
            return entorno._inyector()["_pg_scope_select"](sql, params, self.ambito)

    fuga = anterior(primero, get_conn=lambda: SinProteccion(db_conn, TENANT), pd=pd)
    assert fuga is not None and int(fuga["id"]) == ajeno  # la anomalia es real sobre la base
    r = anterior(primero, get_conn=ns["get_conn"], pd=pd)
    assert r is None or int(r["id"]) in propios


# Clasificacion de cada SQL certificado / NEXT con OR de nivel superior que el inyector alcanzaria (auditoria estatica).
CLASIFICADOS = {
    ("analisis/motor/certificado.py", "asegurar_esquema_investigacion_separado"): "inalcanzable: tarea schema no-op",
    ("analisis/motor/certificado.py", "asegurar_esquema_extension_separado"): "inalcanzable: tarea schema no-op",
    ("analisis/motor/ref/extracted_batch03/readonly_queries.py", "get_periodo_anterior_cronologico"):
        "protegido: solo lo llama el motor de Periodos; en el motor de lectura sin llamador y protegido centralmente",
    ("integraciones/ciclo_periodos/motor/complemento.py", "asegurar_esquema_investigacion_separado"):
        "inalcanzable: tarea schema no-op",
    ("integraciones/ciclo_periodos/motor/complemento.py", "asegurar_esquema_extension_separado"):
        "inalcanzable: tarea schema no-op",
    ("integraciones/ciclo_periodos/motor/ref/b12c/periodo_atomico.py", "<modulo>"): "protegido: S1 duplicado B12C",
    ("integraciones/ciclo_periodos/service.py", "_bloqueos_reversion"):
        "falso positivo: SQL NEXT sin inyector, por ids de periodo ya validados en el ambito",
}


def test_auditoria_estatica_todo_or_de_nivel_superior_esta_clasificado():
    sys.path.insert(0, str(BACKEND))
    import tools_auditar_scope_or as T
    res = T.auditar()
    alcanzables = {(c["archivo"], c["funcion"]) for c in res["casos"] if c["or_nivel_superior"] and any(
        c.get(k, {}).get("vulnerable_si_inyectado") for k in ("tenant", "planes"))}
    assert alcanzables == set(CLASIFICADOS), alcanzables ^ set(CLASIFICADOS)
    assert all(c.get(k, {}).get("protegido_por_proteger_or", True) for c in res["casos"] for k in ("tenant", "planes")
               if c.get(k, {}).get("vulnerable_si_inyectado"))
    assert res["or_dinamicos"] == []
    for nombre in ("asegurar_esquema_investigacion_separado", "asegurar_esquema_extension_separado"):
        from analisis.motor import metadata as A
        from integraciones.ciclo_periodos.motor import metadata as C
        assert A.TAREAS_SISTEMA[nombre] == "schema" and C.TAREAS_SISTEMA[nombre] == "schema"


# ------------------------------------------------------------------------------------------ A1.2 subconsultas
def _tablas():
    inj = entorno._inyector()
    return set(inj["PG_INSTITUTION_TABLES"]), set(inj["PG_DEPARTMENT_TABLES"])


@pytest.mark.parametrize("sql", [
    "SELECT id FROM periodos WHERE anio = ?",
    "SELECT d.id FROM designaciones d LEFT JOIN docentes x ON x.cuil = d.cuil WHERE d.periodo_id = ?",
    "SELECT (SELECT COUNT(*) FROM docentes x WHERE x.institucion_id = p.institucion_id) FROM periodos p",
    "SELECT TRIM(BOTH FROM nombre), EXTRACT(YEAR FROM fecha_alta) FROM docentes",
    "SELECT * FROM (SELECT 1 AS uno) t",
])
def test_subconsultas_sin_tablas_de_ambito_quedan_identicas(sql):
    assert proteger_subconsultas(sql, TENANT, *_tablas()) == sql


def test_subconsultas_reciben_el_ambito_de_la_sesion():
    i, d = _tablas()
    sql = ("SELECT cuil, (SELECT MIN(d0.fecha_desde) FROM designaciones d0 WHERE d0.cuil = docentes.cuil) AS f, "
           "CASE WHEN EXISTS (SELECT 1 FROM designaciones da JOIN periodos pa ON pa.id = da.periodo_id "
           "WHERE da.cuil = docentes.cuil OR da.estado = 'Activa') THEN 1 END, "
           "(SELECT COUNT(*) FROM designaciones x LEFT JOIN docentes y ON y.cuil = x.cuil WHERE x.periodo_id = ?), "
           "(SELECT pult.id FROM periodos pult ORDER BY pult.anio DESC LIMIT 1) FROM docentes WHERE cuil = ?")
    q = proteger_subconsultas(sql, TENANT, i, d)
    assert "WHERE (d0.cuil = docentes.cuil) AND d0.institucion_id = 1 AND d0.departamento_id = 1)" in q
    assert ("WHERE (da.cuil = docentes.cuil OR da.estado = 'Activa') AND da.institucion_id = 1 AND da.departamento_id = 1 "
            "AND pa.institucion_id = 1 AND pa.departamento_id = 1)") in q
    assert "LEFT JOIN docentes y ON (y.cuil = x.cuil) AND y.institucion_id = 1 AND y.departamento_id = 1 WHERE" in q
    assert "FROM periodos pult WHERE pult.institucion_id = 1 AND pult.departamento_id = 1 ORDER BY" in q
    assert q.count("?") == sql.count("?") and q.endswith("FROM docentes WHERE cuil = ?")  # nivel superior: inyector
    planes = proteger_subconsultas("SELECT (SELECT COUNT(*) FROM proyectos_investigacion p) FROM materias",
                                   {"kind": "planes", "institucion_id": 3}, i, d)
    assert "FROM proyectos_investigacion p WHERE p.institucion_id = 3" in planes


def test_subconsulta_no_garantizable_falla_cerrado():
    with pytest.raises(AmbitoNoGarantizable):
        proteger_subconsultas("SELECT (SELECT COUNT(*) FROM designaciones d WHERE a = 1 UNION SELECT 1 FROM periodos "
                              "WHERE b = 2) FROM docentes", TENANT, *_tablas())


def test_ambos_motores_aplican_el_ambito_en_subconsultas():
    from integraciones.ciclo_periodos.entorno import _TenantConn
    sql = "SELECT (SELECT MIN(d0.fecha_desde) FROM designaciones d0 WHERE d0.cuil = docentes.cuil) FROM docentes"
    for conn in (entorno._Conexion(None, TENANT), _TenantConn(None, TENANT)):
        q, _ = conn.preparar(sql, [])
        assert "d0.institucion_id = 1 AND d0.departamento_id = 1" in q and "docentes.institucion_id = %s" in q


def _cuil_compartible(db_conn) -> str:
    """CUIL de un docente del dep 1 (no se imprime; dato real solo dentro de la transaccion del test)."""
    return db_conn.execute("SELECT cuil FROM docentes WHERE institucion_id = 1 AND departamento_id = 1 "
                           "AND cuil IS NOT NULL ORDER BY id LIMIT 1").fetchone()[0]


def test_fuga_real_bloqueada_en_el_resumen_docente(db_conn):
    """Sintetico (ROLLBACK): una designacion de 1990 del MISMO CUIL en otro tenant (inst 2 / dep 5).  Con el inyector
    certificado la ficha del Resumen del dep 1 toma esa fecha ajena; con el entorno NEXT no."""
    cuil = _cuil_compartible(db_conn)
    db_conn.execute("INSERT INTO designaciones (institucion_id, departamento_id, cuil, cargo, estado, fecha_desde, "
                    "fecha_hasta, observaciones) VALUES (2, 5, %s, 'ZZE5', 'Finalizada', '1990-01-01', '1990-06-30', "
                    "'ZZE5')", [cuil])
    ns = motor(db_conn, 1, 1)

    class SinProteccion(entorno._Conexion):
        def preparar(self, sql, params):
            return entorno._inyector()["_pg_scope_select"](sql, params, self.ambito)

    base = ns["_get_resumen_docente_base_v95"]  # entry l. 5004 (el SQL con las subconsultas por CUIL)
    assert base.__code__.co_firstlineno == 1394
    certificado = dict(base.__globals__)
    certificado["get_conn"] = lambda: SinProteccion(db_conn, TENANT)
    fuga = type(base)(base.__code__, certificado)(cuil)
    assert str(fuga[0]["fecha_inicio_historica"].iloc[0]) == "1990-01-01"  # la anomalia es real
    propio = ns["get_resumen_docente"](cuil)[0]  # cadena completa del Resumen (v95 -> v162)
    assert str(propio["fecha_inicio_historica"].iloc[0]) != "1990-01-01"


SUBCONSULTAS_RIESGO = {
    ("analisis/motor/certificado.py", "get_resumen_docente"): "VULNERABLE (alcanzable, CUIL): corregido",
    ("analisis/motor/certificado.py", "get_designaciones"): "codigo muerto (v229 redefinida); cubierto",
    ("integraciones/ciclo_periodos/motor/complemento.py", "get_designaciones"): "codigo muerto; cubierto",
    ("analisis/motor/certificado.py", "_get_horarios_docente_periodo_pg_global"):
        "falso positivo: JOIN por asignacion_id contra el CTE base (con ambito explicito), _pg_read_dataframe",
    ("analisis/motor/certificado.py", "_consulta_horarios_bulk_v194"): "falso positivo: idem (CTE base)",
    ("comisiones/proyectos.py", "<modulo>"): "falso positivo: idem (CTE base), SQL NEXT con ambito explicito",
}


def test_auditoria_estatica_de_subconsultas_clasificada():
    sys.path.insert(0, str(BACKEND))
    import tools_auditar_scope_subconsultas as S
    riesgo = {(h["archivo"], h["funcion"]) for h in S.auditar()["hallazgos"]
              if h["clase"] not in ("clave_tecnica", "parametro_tecnico")}
    assert riesgo == set(SUBCONSULTAS_RIESGO), riesgo ^ set(SUBCONSULTAS_RIESGO)


def test_get_designaciones_v229_es_codigo_muerto():
    """La subconsulta sin correlacion de ``get_designaciones`` v229 (entry l. 4742, "ultimo periodo del departamento"
    tomado de TODOS los periodos) es inalcanzable: la redefinicion de l. 32479 la reemplaza antes de que un alias la
    capture, en el motor de lectura y en el de Periodos.  Igual queda cubierta por ``proteger_subconsultas``."""
    import analisis.motor as am
    from integraciones.ciclo_periodos import motor as cm
    for archivo in (Path(am.__file__).parent / "certificado.py", Path(cm.__file__).parent / "complemento.py"):
        lineas = archivo.read_text(encoding="utf-8").splitlines()
        defs = [k for k, l in enumerate(lineas) if l.startswith("def get_designaciones(")]
        alias = [k for k, l in enumerate(lineas) if re.match(r"\w+ = get_designaciones$", l)]
        v229 = next(k for k in defs if any("pult" in l for l in lineas[k:k + 50]))
        siguiente = min(k for k in defs if k > v229)
        assert not [k for k in alias if v229 < k < siguiente], archivo.name


# ------------------------------------------------------------------------------------------ A4 rutas
PUBLICAS = {("POST", "/auth/login"), ("POST", "/auth/logout"), ("GET", "/health")}


class _Trampa:
    def __init__(self, nombre, toques):
        self._nombre, self._toques = nombre, toques

    def __getattr__(self, k):
        self._toques.append(f"{self._nombre}.{k}")
        raise AssertionError("servicio alcanzado sin sesion/CSRF")


class _AuthStub:
    def __init__(self, toques):
        self.toques = toques

    def validate(self, token):
        from auth import core
        from auth.service import SessionEnded, SessionRecord
        if token != "tok-valido":
            raise SessionEnded(core.END_NO_IDENTITY)
        return SessionRecord(user={"id": 3, "rol": "usuario_departamento", "institucion_id": 1, "departamento_id": 1},
                             meta={}, scope={"institucion_id": 1, "departamento_id": 1})

    def __getattr__(self, k):
        self.toques.append(f"auth.{k}")
        raise AssertionError("auth alcanzado mas alla de validate")


def _rutas(app):
    def walk(routes):
        for r in routes:
            if isinstance(r, APIRoute):
                yield r
            elif hasattr(r, "original_router"):
                yield from walk(r.original_router.routes)
    return sorted({(m, r.path) for r in walk(app.routes) for m in r.methods})


@pytest.fixture
def app_trampa():
    import main
    app, toques = main.app, []
    nombres = ["auth", "pool"] + sorted(set(re.findall(r"app\.state\.(\w+) = ", (BACKEND / "main.py").read_text(
        encoding="utf-8-sig"))) - {"auth", "pool"})
    previo = {n: getattr(app.state, n) for n in nombres if hasattr(app.state, n)}
    for n in nombres:
        setattr(app.state, n, _Trampa(n, toques))
    app.state.auth = _AuthStub(toques)
    try:
        yield app, toques, TestClient(app, raise_server_exceptions=False)
    finally:
        for n in nombres:
            if n in previo:
                setattr(app.state, n, previo[n])
            else:
                delattr(app.state, n)


def test_inventario_de_rutas(app_trampa):
    app, _, _ = app_trampa
    rutas = _rutas(app)
    assert len(rutas) >= 269 and not [p for _, p in rutas if "{" in p]


def test_toda_ruta_exige_sesion(app_trampa):
    app, toques, client = app_trampa
    malas = []
    for metodo, path in _rutas(app):
        if (metodo, path) in PUBLICAS:
            continue
        r = client.request(metodo, path, json={"institucion_id": 2, "departamento_id": 5},
                           headers={"x-deptit-request": "1"})
        if r.status_code != 401:
            malas.append((metodo, path, r.status_code))
    assert malas == [] and toques == []


def test_toda_escritura_exige_csrf(app_trampa):
    app, toques, client = app_trampa
    client.cookies.set("deptit_session", "tok-valido")
    malas = []
    for metodo, path in _rutas(app):
        if metodo == "GET" or (metodo, path) == ("GET", "/health"):
            continue
        r = client.request(metodo, path, json={})
        if r.status_code != 403 or r.json()["error"]["code"] != "CSRF":
            malas.append((metodo, path, r.status_code))
    assert malas == [] and toques == []


def test_system_info_solo_superadmin(app_trampa):
    """``GET /system/info`` (conteos globales de todos los tenants) ya no es publico: sin sesion 401, con sesion de
    departamento 403, sin tocar la base."""
    _, toques, client = app_trampa
    assert client.get("/system/info").status_code == 401
    client.cookies.set("deptit_session", "tok-valido")
    r = client.get("/system/info")
    assert r.status_code == 403 and r.json()["error"]["code"] == "DENIED" and toques == []


def test_ningun_body_fuera_de_auth_y_saas_define_el_ambito():
    """El ambito sale SIEMPRE de la sesion: ningun modelo de body declara institucion/departamento (salvo Auth
    ``PUT /auth/context``, validado por la politica, y SaaS, solo superadmin) y ningun servicio lo lee del payload."""
    campos = []
    for ruta in BACKEND.rglob("routes.py"):
        rel = ruta.relative_to(BACKEND).as_posix()
        if rel.startswith((".venv", "auth/", "saas/")):
            continue
        for m in re.finditer(r"^\s+(\w*(?:institucion|departamento)\w*)\s*:", ruta.read_text(encoding="utf-8-sig"),
                             re.M):
            campos.append((rel, m.group(1)))
    assert campos == [("docentes/routes.py", "departamento_origen")]  # texto del departamento de origen del prestamo
    lectores = []
    patron = re.compile(r"\b(?:datos|payload|body|data|form|params)\s*(?:\.get\(|\[)\s*[\"'](institucion_id|"
                        r"departamento_id)[\"']")
    for ruta in BACKEND.rglob("*.py"):
        rel = ruta.relative_to(BACKEND).as_posix()
        if rel.startswith((".venv", "tests/", "saas/", "auth/")) or "/motor/" in rel or "_motor/" in rel \
                or "/ref" in rel or rel.startswith("tools_"):
            continue
        if patron.search(ruta.read_text(encoding="utf-8-sig")):
            lectores.append(rel)
    assert lectores == []


def _allowlists():
    """(metodo, ruta backend) que cada proxy Next reenvia: ALLOWED + rutas especiales (multipart, binarios)."""
    out = set()
    for f in sorted(FRONT_API.glob("*/*/route.ts")):
        src = f.read_text(encoding="utf-8")
        m = re.search(r'forwardToBackend\(request, "([^"]+)"', src)
        if not m:
            continue
        prefijo = m.group(1)
        entradas = []
        if "Object.fromEntries" in src:  # SaaS: lista de rutas POST + ALLOWED[""]
            lista = re.search(r"Object\.fromEntries\(\s*\[(.*?)\]\.map", src, re.S).group(1)
            entradas += [(k, '"POST"') for k in re.findall(r'"([^"]+)"', lista)]
            entradas += re.findall(r'ALLOWED\["([^"]*)"\] = \[([^\]]*)\]', src)
        else:
            ini = src.index("{", src.index("const ALLOWED"))
            nivel, fin = 0, ini
            for fin in range(ini, len(src)):
                nivel += {"{": 1, "}": -1}.get(src[fin], 0)
                if nivel == 0:
                    break
            bloque = re.sub(r"//[^\n]*", "", src[ini:fin + 1])
            constantes = dict(re.findall(r"const (\w+) = \[([^\]]*)\] as const;", src))
            entradas += [((a or b), c if c else constantes[n]) for a, b, c, n in
                         re.findall(r'[{,]\s*(?:"([^"]*)"|([\w-]+)):\s*(?:\[([^\]]*)\]|(\w+))', bloque)]
        for k, metodos in entradas:
            for metodo in re.findall(r'"(\w+)"', metodos):
                out.add((metodo, f"/{prefijo}" + (f"/{k}" if k else "")))
        for conjunto in re.findall(r"new Set\(\[([^\]]*)\]\)", src):
            for k in re.findall(r'"([^"]+)"', conjunto):
                out.add(("POST", f"/{prefijo}/{k}"))
        for k in re.findall(r'request\.method === "POST" && route === "([^"]+)"', src):
            out.add(("POST", f"/{prefijo}/{k}"))
        for k in re.findall(r'request\.method === "GET" && route === "([^"]+)"', src):
            out.add(("GET", f"/{prefijo}/{k}"))
    return out


def test_proxies_next_solo_exponen_rutas_existentes():
    import main
    backend = set(_rutas(main.app))
    expuestas = _allowlists()
    assert len(expuestas) >= 250
    assert sorted(expuestas - backend) == []


def test_proxies_next_validan_mismo_origen_en_cada_post_propio():
    for f in sorted(FRONT_API.rglob("route.ts")):
        src = f.read_text(encoding="utf-8")
        for bloque in re.split(r"\n(?=(?:async )?function )", src):
            if re.search(r'method: "POST"', bloque):
                assert "sameOrigin(request)" in bloque, (f.parent.name, bloque.splitlines()[0])
        if "forwardToBackend" not in src and "auth" not in str(f) and "backend-health" not in str(f):
            raise AssertionError(f"proxy sin forwardToBackend: {f}")
    texto = (BACKEND.parent / "frontend" / "src" / "lib" / "backend-proxy.ts").read_text(encoding="utf-8")
    assert 'if (method !== "GET" && !sameOrigin(request))' in texto and '"x-deptit-request"' in texto
    assert "Sin query string" in texto
